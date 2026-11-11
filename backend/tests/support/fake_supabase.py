"""Test double for the Supabase Auth (GoTrue) and Storage HTTP APIs.

It implements only the endpoints the backend calls, with the same request and response
shapes, so tests exercise the real SupabaseAuthProvider and SupabaseStorageProvider code.
Users and sessions are written to the test database (auth.users, auth.sessions) so that the
profile trigger and the backend's session checks run for real. Emails are captured in an
outbox instead of being sent.

TEST USE ONLY. It is not imported by application code.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

ACCESS_TTL = 3600


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**12, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def _check_password(password: str, stored: str) -> bool:
    raw = base64.b64decode(stored)
    return secrets.compare_digest(_hash_password(password, raw[:16]), stored)


def _weak(password: str) -> bool:
    return len(password) < 8 or not (
        re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"\d", password)
    )


@dataclass
class FakeUser:
    id: str
    email: str
    password_hash: str
    confirmed: bool = False
    banned: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboxEmail:
    to: str
    kind: str  # "signup" | "recovery"
    token_hash: str


@dataclass
class _OneTimeToken:
    user_id: str
    kind: str
    expires_at: datetime
    used: bool = False


class FakeSupabase:
    def __init__(
        self,
        *,
        database_url: str,
        jwt_secret: str,
        anon_key: str,
        service_role_key: str,
    ) -> None:
        self.jwt_secret = jwt_secret
        self.anon_key = anon_key
        self.service_role_key = service_role_key
        # NullPool: each test runs on its own event loop.
        self._engine = create_async_engine(
            database_url, poolclass=NullPool, connect_args={"statement_cache_size": 0}
        )
        self.users: dict[str, FakeUser] = {}  # by email
        self.outbox: list[OutboxEmail] = []
        self.objects: dict[str, tuple[bytes, str]] = {}
        self._tokens: dict[str, _OneTimeToken] = {}
        self._refresh: dict[str, tuple[str, str]] = {}  # token -> (user_id, session_id)
        self.fail_next: set[str] = set()  # operation names that should answer 500 once
        self.app = self._build_app()

    # -- helpers used by tests ---------------------------------------------------------

    def last_email(self, to: str, kind: str) -> OutboxEmail:
        for email in reversed(self.outbox):
            if email.to == to and email.kind == kind:
                return email
        raise AssertionError(f"no {kind} email to {to}")

    def user_by_id(self, user_id: str) -> FakeUser:
        return next(u for u in self.users.values() if u.id == user_id)

    async def create_confirmed_user(self, email: str, password: str, display_name: str) -> str:
        user = await self._create_user(email, password, {"display_name": display_name})
        user.confirmed = True
        return user.id

    def expire_tokens(self) -> None:
        for token in self._tokens.values():
            token.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    async def aclose(self) -> None:
        await self._engine.dispose()

    # -- internals ---------------------------------------------------------------------

    async def _create_user(self, email: str, password: str, metadata: dict[str, Any]) -> FakeUser:
        user = FakeUser(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=_hash_password(password, secrets.token_bytes(16)),
            metadata=metadata,
        )
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "insert into auth.users (id, email, raw_user_meta_data) "
                    "values (:id, :email, cast(:meta as jsonb))"
                ),
                {"id": user.id, "email": email, "meta": json.dumps(metadata)},
            )
        self.users[email] = user
        return user

    def _issue_token(self, user: FakeUser, kind: str, ttl: timedelta) -> str:
        # A new link invalidates earlier ones of the same kind (FR-AUTH-002 AC4).
        for token in self._tokens.values():
            if token.user_id == user.id and token.kind == kind:
                token.used = True
        token_hash = secrets.token_hex(28)
        self._tokens[token_hash] = _OneTimeToken(user.id, kind, datetime.now(UTC) + ttl)
        self.outbox.append(OutboxEmail(to=user.email, kind=kind, token_hash=token_hash))
        return token_hash

    async def _new_session(self, user: FakeUser) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "insert into auth.sessions (id, user_id, user_agent, ip) "
                    "values (:id, :uid, :ua, '203.0.113.7')"
                ),
                {
                    "id": session_id,
                    "uid": user.id,
                    "ua": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0",
                },
            )
        return self._session_body(user, session_id)

    def _session_body(self, user: FakeUser, session_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        access = jwt.encode(
            {
                "sub": user.id,
                "aud": "authenticated",
                "role": "authenticated",
                "email": user.email,
                "session_id": session_id,
                "iat": now,
                "exp": now + timedelta(seconds=ACCESS_TTL),
                "app_metadata": {},
                "user_metadata": user.metadata,
            },
            self.jwt_secret,
            algorithm="HS256",
        )
        refresh = secrets.token_urlsafe(24)
        self._refresh[refresh] = (user.id, session_id)
        return {
            "access_token": access,
            "token_type": "bearer",
            "expires_in": ACCESS_TTL,
            "refresh_token": refresh,
            "user": {"id": user.id, "email": user.email},
        }

    async def _session_exists(self, session_id: str) -> bool:
        async with self._engine.begin() as conn:
            row = (
                await conn.execute(
                    text("select 1 from auth.sessions where id = :id"), {"id": session_id}
                )
            ).first()
        return row is not None

    def _claims(self, request: Request) -> dict[str, Any] | None:
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return None
        try:
            return jwt.decode(
                header[7:], self.jwt_secret, algorithms=["HS256"], audience="authenticated"
            )
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def _error(status: int, code: str) -> JSONResponse:
        return JSONResponse({"error_code": code, "msg": code}, status_code=status)

    # -- app ---------------------------------------------------------------------------

    def _build_app(self) -> FastAPI:
        app = FastAPI()
        fake = self

        @app.middleware("http")
        async def check_apikey(request: Request, call_next: Any) -> Response:
            public_download = request.method == "GET" and (
                request.url.path.startswith("/storage/v1/object/sign/")
                or request.url.path == "/__outbox"
            )
            known_key = request.headers.get("apikey") in (fake.anon_key, fake.service_role_key)
            if not known_key and not public_download:
                return fake._error(401, "no_api_key")
            op = request.url.path.rsplit("/", 1)[-1]
            if op in fake.fail_next:
                fake.fail_next.discard(op)
                return fake._error(500, "unexpected_failure")
            return await call_next(request)  # type: ignore[no-any-return]

        @app.post("/auth/v1/signup")
        async def signup(request: Request) -> Response:
            body = await request.json()
            email, password = body["email"].lower(), body["password"]
            if _weak(password):
                return fake._error(422, "weak_password")
            if email in fake.users:
                # GoTrue with confirmations on: an obfuscated user and no email.
                return JSONResponse({"id": str(uuid.uuid4()), "email": email})
            user = await fake._create_user(email, password, body.get("data") or {})
            fake._issue_token(user, "signup", timedelta(hours=24))
            return JSONResponse({"id": user.id, "email": email})

        @app.post("/auth/v1/token")
        async def token(request: Request) -> Response:
            body = await request.json()
            grant = request.query_params.get("grant_type")
            if grant == "password":
                user = fake.users.get(str(body.get("email", "")).lower())
                if (
                    user is None
                    or user.banned
                    or not _check_password(body["password"], user.password_hash)
                ):
                    return fake._error(400, "invalid_credentials")
                if not user.confirmed:
                    return fake._error(400, "email_not_confirmed")
                return JSONResponse(await fake._new_session(user))
            if grant == "refresh_token":
                entry = fake._refresh.pop(body.get("refresh_token", ""), None)
                if entry is None or not await fake._session_exists(entry[1]):
                    return fake._error(400, "refresh_token_not_found")
                user = fake.user_by_id(entry[0])
                if user.banned:
                    return fake._error(400, "user_banned")
                return JSONResponse(fake._session_body(user, entry[1]))
            return fake._error(400, "unsupported_grant_type")

        @app.post("/auth/v1/logout")
        async def logout(request: Request) -> Response:
            claims = fake._claims(request)
            if claims is None:
                return fake._error(401, "bad_jwt")
            scope = request.query_params.get("scope", "global")
            sql = {
                "local": "delete from auth.sessions where id = :sid",
                "global": "delete from auth.sessions where user_id = :uid",
                "others": "delete from auth.sessions where user_id = :uid and id <> :sid",
            }[scope]
            async with fake._engine.begin() as conn:
                await conn.execute(text(sql), {"sid": claims["session_id"], "uid": claims["sub"]})
            return Response(status_code=204)

        @app.post("/auth/v1/recover")
        async def recover(request: Request) -> Response:
            user = fake.users.get((await request.json())["email"].lower())
            if user is not None and not user.banned:
                fake._issue_token(user, "recovery", timedelta(hours=1))
            return JSONResponse({})

        @app.post("/auth/v1/resend")
        async def resend(request: Request) -> Response:
            user = fake.users.get((await request.json())["email"].lower())
            if user is not None and not user.confirmed:
                fake._issue_token(user, "signup", timedelta(hours=24))
            return JSONResponse({})

        @app.post("/auth/v1/verify")
        async def verify(request: Request) -> Response:
            body = await request.json()
            entry = fake._tokens.get(body.get("token_hash", ""))
            if (
                entry is None
                or entry.used
                or entry.kind != body.get("type")
                or entry.expires_at <= datetime.now(UTC)
            ):
                return fake._error(403, "otp_expired")
            entry.used = True
            user = fake.user_by_id(entry.user_id)
            if entry.kind == "signup":
                user.confirmed = True
            return JSONResponse(await fake._new_session(user))

        @app.put("/auth/v1/user")
        async def update_user(request: Request) -> Response:
            claims = fake._claims(request)
            if claims is None or not await fake._session_exists(claims["session_id"]):
                return fake._error(401, "bad_jwt")
            user = fake.user_by_id(claims["sub"])
            password = (await request.json()).get("password", "")
            if _weak(password):
                return fake._error(422, "weak_password")
            if _check_password(password, user.password_hash):
                return fake._error(422, "same_password")
            user.password_hash = _hash_password(password, secrets.token_bytes(16))
            return JSONResponse({"id": user.id})

        @app.put("/auth/v1/admin/users/{user_id}")
        async def admin_update(user_id: str, request: Request) -> Response:
            if request.headers.get("apikey") != fake.service_role_key:
                return fake._error(403, "not_admin")
            body = await request.json()
            user = fake.user_by_id(user_id)
            # Memory only: the backend calls this inside its own database transaction.
            user.banned = bool(body.get("ban_duration"))
            if "email" in body:
                fake.users.pop(user.email, None)
                user.email = body["email"]
                fake.users[user.email] = user
            return JSONResponse({"id": user.id})

        # -- test-only: lets an out-of-process driver read "sent" emails ------------------

        @app.get("/__outbox")
        async def outbox(to: str) -> Response:
            return JSONResponse(
                [
                    {"kind": email.kind, "token_hash": email.token_hash}
                    for email in fake.outbox
                    if email.to == to.lower()
                ]
            )

        # -- storage ---------------------------------------------------------------------

        @app.post("/storage/v1/object/sign/{bucket}/{path:path}")
        async def sign(bucket: str, path: str, request: Request) -> Response:
            if f"{bucket}/{path}" not in fake.objects:
                return fake._error(400, "not_found")
            return JSONResponse({"signedURL": f"/object/sign/{bucket}/{path}?token=fake"})

        @app.get("/storage/v1/object/sign/{bucket}/{path:path}")
        async def download(bucket: str, path: str) -> Response:
            item = fake.objects.get(f"{bucket}/{path}")
            if item is None:
                return fake._error(404, "not_found")
            return Response(item[0], media_type=item[1])

        @app.post("/storage/v1/object/{bucket}/{path:path}")
        async def upload(bucket: str, path: str, request: Request) -> Response:
            if request.headers.get("apikey") != fake.service_role_key:
                return fake._error(403, "forbidden")
            fake.objects[f"{bucket}/{path}"] = (
                await request.body(),
                request.headers.get("content-type", "application/octet-stream"),
            )
            return JSONResponse({"Key": f"{bucket}/{path}"})

        @app.delete("/storage/v1/object/{bucket}/{path:path}")
        async def delete(bucket: str, path: str) -> Response:
            if fake.objects.pop(f"{bucket}/{path}", None) is None:
                return fake._error(400, "not_found")
            return JSONResponse({"message": "deleted"})

        return app
