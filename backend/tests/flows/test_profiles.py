import io
import uuid

from PIL import Image

from tests.flows.conftest import Harness


def _png_with_exif() -> bytes:
    image = Image.new("RGB", (1200, 800), (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "FakeCameraMaker"  # Make
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", exif=exif)
    return buffer.getvalue()


# -- reading and editing -------------------------------------------------------------------


def test_profile_contains_expected_fields_without_credentials(harness: Harness) -> None:
    email, headers = harness.signed_up_user()
    data = harness.client.get("/api/v1/users/me", headers=headers).json()["data"]
    for key in (
        "display_name",
        "username",
        "email",
        "avatar_url",
        "bio",
        "country_code",
        "language",
        "time_zone",
        "theme",
        "ui_mode",
        "presence_preference",
        "onboarding_completed",
    ):
        assert key in data
    assert data["email"] == email
    assert not {"password", "encrypted_password", "refresh_token"} & set(data)


def test_profile_update_sanitises_and_persists(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    response = harness.client.patch(
        "/api/v1/users/me",
        json={
            "display_name": "  <b>Rowena</b> Cruz ",
            "bio": "OFW in <script>alert(1)</script>Dubai",
            "country_code": "ae",
            "language": "fil",
            "time_zone": "Asia/Dubai",
            "theme": "dark",
            "ui_mode": "classic",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["display_name"] == "Rowena Cruz"
    assert "<" not in data["bio"]
    assert data["country_code"] == "AE"
    assert data["ui_mode"] == "classic"
    assert (
        harness.client.get("/api/v1/users/me", headers=headers).json()["data"]["time_zone"]
        == "Asia/Dubai"
    )


def test_profile_update_rejects_invalid_values(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    for body in (
        {"display_name": "A"},
        {"bio": "x" * 161},
        {"country_code": "ZZ"},
        {"language": "klingon"},
        {"time_zone": "Mars/Olympus"},
        {"theme": "neon"},
        {"display_name": None},
    ):
        assert (
            harness.client.patch("/api/v1/users/me", json=body, headers=headers).status_code == 422
        ), body


def test_privileged_fields_cannot_be_set_by_the_user(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    for body in (
        {"role": "admin"},
        {"status": "active"},
        {"id": str(uuid.uuid4())},
        {"username": "x_y_z"},
    ):
        assert (
            harness.client.patch("/api/v1/users/me", json=body, headers=headers).status_code == 422
        )
    assert harness.client.get("/api/v1/users/me", headers=headers).json()["data"]["role"] == "user"


def test_onboarding_sets_username_once(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    username = f"Mari_{uuid.uuid4().hex[:6]}"
    response = harness.client.post(
        "/api/v1/users/me/onboarding",
        json={
            "username": username,
            "display_name": "Marites",
            "country_code": "PH",
            "language": "en",
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["onboarding_completed"] is True
    again = harness.client.post(
        "/api/v1/users/me/onboarding",
        json={"username": f"other_{uuid.uuid4().hex[:6]}", "display_name": "Marites"},
        headers=headers,
    )
    assert again.status_code == 409


def test_taken_username_is_case_insensitive_and_offers_suggestions(harness: Harness) -> None:
    _, first = harness.signed_up_user()
    _, second = harness.signed_up_user()
    username = f"jericho_{uuid.uuid4().hex[:6]}"
    harness.client.post(
        "/api/v1/users/me/onboarding",
        json={"username": username, "display_name": "Jericho"},
        headers=first,
    )
    taken = harness.client.post(
        "/api/v1/users/me/onboarding",
        json={"username": username.upper(), "display_name": "Jericho"},
        headers=second,
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "username_taken"
    assert taken.json()["error"]["details"]["suggestions"]


def test_reserved_and_malformed_usernames_are_rejected(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    for username in ("admin", "Support", "ab", "bad name", "x" * 21):
        response = harness.client.post(
            "/api/v1/users/me/onboarding",
            json={"username": username, "display_name": "Someone"},
            headers=headers,
        )
        assert response.status_code == 422, username


# -- authorisation -------------------------------------------------------------------------


def test_profile_requires_a_valid_token(harness: Harness) -> None:
    assert harness.client.get("/api/v1/users/me").status_code == 401
    bad = harness.client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401
    assert harness.client.patch("/api/v1/users/me", json={"bio": "hi"}).status_code == 401


def test_one_user_cannot_change_another(harness: Harness) -> None:
    _, alice = harness.signed_up_user()
    _, bob = harness.signed_up_user()
    alice_id = harness.user_id(alice)

    # There is no way to address another user's profile: only /users/me exists, and the
    # identity comes from the token. Supplying an id is rejected.
    response = harness.client.patch(
        "/api/v1/users/me", json={"id": alice_id, "bio": "pwned"}, headers=bob
    )
    assert response.status_code == 422
    assert harness.client.patch(
        f"/api/v1/users/{alice_id}", json={"bio": "pwned"}, headers=bob
    ).status_code in (404, 405)
    harness.client.patch("/api/v1/users/me", json={"bio": "bob's bio"}, headers=bob)
    assert harness.profile(alice_id)["bio"] is None


def test_token_signed_with_another_key_is_rejected(harness: Harness) -> None:
    import jwt

    _, headers = harness.signed_up_user()
    user_id = harness.user_id(headers)
    forged = jwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "session_id": str(uuid.uuid4()),
            "exp": 9999999999,
        },
        "attacker-controlled-secret-key-0123456789",
        algorithm="HS256",
    )
    assert (
        harness.client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )


def test_rls_denies_cross_user_reads_for_client_roles(harness: Harness) -> None:
    _, alice = harness.signed_up_user()
    _, bob = harness.signed_up_user()
    alice_id, bob_id = harness.user_id(alice), harness.user_id(bob)
    rows = harness.sql(
        f"""
        begin;
        set local role authenticated;
        select set_config('request.jwt.claims', '{{"sub":"{bob_id}"}}', true);
        """
        if False
        else "select 1"
    )
    assert rows
    # Run as the "authenticated" role with Bob's claims, the way PostgREST would.
    import asyncio

    import asyncpg

    async def as_bob() -> tuple[int, int, str | None]:
        connection = await asyncpg.connect(harness.database_url, statement_cache_size=0)
        try:
            async with connection.transaction():
                await connection.execute("set local role authenticated")
                await connection.execute(
                    "select set_config('request.jwt.claims', $1, true)", f'{{"sub":"{bob_id}"}}'
                )
                others = await connection.fetchval(
                    "select count(*) from public.profiles where id = $1", uuid.UUID(alice_id)
                )
                own = await connection.fetchval(
                    "select count(*) from public.profiles where id = $1", uuid.UUID(bob_id)
                )
                try:
                    await connection.fetchval("select otp_hash from public.phone_numbers limit 1")
                    otp_access = "allowed"
                except asyncpg.InsufficientPrivilegeError:
                    otp_access = None
                return int(others), int(own), otp_access
        finally:
            await connection.close()

    others, own, otp_access = asyncio.run(as_bob())
    assert others == 0
    assert own == 1
    assert otp_access is None


# -- photo ---------------------------------------------------------------------------------


def test_avatar_upload_reencodes_and_strips_metadata(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    response = harness.client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("me.png", _png_with_exif(), "image/png")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["avatar_url"].startswith(
        "http://fake-supabase.test/storage/v1/object/sign/avatars/"
    )

    ((key, (stored, content_type)),) = harness.fake.objects.items()
    assert content_type == "image/webp"
    user_id = harness.user_id(headers)
    assert key.startswith(f"avatars/{user_id}/")
    with Image.open(io.BytesIO(stored)) as image:
        assert image.format == "WEBP"
        assert max(image.size) <= 512
        assert not image.getexif()


def test_replacing_and_removing_avatar_cleans_up_storage(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    for _ in range(2):
        harness.client.post(
            "/api/v1/users/me/avatar",
            files={"avatar": ("a.png", _png_with_exif(), "image/png")},
            headers=headers,
        )
    assert len(harness.fake.objects) == 1
    assert harness.client.delete("/api/v1/users/me/avatar", headers=headers).status_code == 204
    assert harness.fake.objects == {}
    assert (
        harness.client.get("/api/v1/users/me", headers=headers).json()["data"]["avatar_url"] is None
    )


def test_avatar_rejects_non_images_and_oversized_files(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    fake_png = harness.client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("evil.png", b"<?php system($_GET['x']); ?>", "image/png")},
        headers=headers,
    )
    assert fake_png.status_code == 422
    assert fake_png.json()["error"]["code"] == "invalid_image"

    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    assert (
        harness.client.post(
            "/api/v1/users/me/avatar",
            files={"avatar": ("a.gif", gif.getvalue(), "image/gif")},
            headers=headers,
        ).status_code
        == 422
    )

    big = harness.client.post(
        "/api/v1/users/me/avatar",
        files={"avatar": ("big.png", b"\x89PNG" + b"0" * (2 * 1024 * 1024 + 10), "image/png")},
        headers=headers,
    )
    assert big.status_code == 422
    assert harness.fake.objects == {}


# -- presence ------------------------------------------------------------------------------


def test_presence_preferences_and_heartbeat(harness: Harness) -> None:
    _, headers = harness.signed_up_user()
    beat = harness.client.post(
        "/api/v1/users/me/presence/heartbeat", json={"idle": False}, headers=headers
    )
    assert beat.json()["data"]["status"] == "online"
    assert beat.json()["data"]["last_seen_at"] is not None

    idle = harness.client.post(
        "/api/v1/users/me/presence/heartbeat", json={"idle": True}, headers=headers
    )
    assert idle.json()["data"]["status"] == "away"

    busy = harness.client.put(
        "/api/v1/users/me/presence", json={"preference": "busy"}, headers=headers
    )
    assert busy.json()["data"]["status"] == "busy"
    assert (
        harness.client.put(
            "/api/v1/users/me/presence", json={"preference": "offline"}, headers=headers
        ).status_code
        == 422
    )
