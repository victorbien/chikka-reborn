"""Tests for the Kiro hook checks. Run: backend\\.venv\\Scripts\\python.exe -m pytest scripts/hooks/tests -q

Fake credentials are assembled at runtime so this file does not trip the secrets scanner itself.
"""

import json

import architecture
import common
import guards
import hookcheck
import pytest
import security
from common import Finding
from routes import parse_routes

FAKE_JWT = "eyJ" + "a" * 20 + ".eyJ" + "b" * 12 + "." + "c" * 12
FAKE_SID = "AC" + "0" * 32
FAKE_AWS = "AKIA" + "A" * 16


def tool_input(**values: str) -> str:
    return json.dumps({"tool_name": "fs_write", "tool_input": values})


def decision(capsys: pytest.CaptureFixture[str]) -> str | None:
    out = capsys.readouterr().out.strip()
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


# -- write guard -----------------------------------------------------------------------------


@pytest.mark.parametrize("secret", [FAKE_JWT, FAKE_SID, FAKE_AWS])
def test_write_with_a_credential_is_blocked(
    secret: str, capsys: pytest.CaptureFixture[str]
) -> None:
    raw = tool_input(path="backend/app/x.py", text=f'KEY = "{secret}"')
    assert guards.guard_write(raw) == 2
    assert secret not in capsys.readouterr().err


def test_credential_shaped_fixture_in_a_test_file_is_allowed() -> None:
    raw = tool_input(path="backend/tests/unit/test_x.py", text=f'TOKEN = "{FAKE_JWT}"')
    assert guards.guard_write(raw) == 0


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("backend/.env", "ask"),
        (".env.production", "ask"),
        ("backend/production.env", "ask"),
        ("backend/.env.example", None),
        ("backend/production.env.example", None),
        (".kiro/hooks/lint.json", "ask"),
        (".kiro/steering/security.md", "ask"),
        ("scripts/hooks/guards.py", "ask"),
        ("backend/app/core/config.py", None),
    ],
)
def test_write_paths(path: str, expected: str | None, capsys: pytest.CaptureFixture[str]) -> None:
    assert guards.guard_write(tool_input(path=path, text="x = 1")) == 0
    assert decision(capsys) == expected


def test_editing_a_committed_migration_asks_but_a_new_one_does_not(
    capsys: pytest.CaptureFixture[str],
) -> None:
    committed = "supabase/migrations/20261110000001_foundation.sql"
    assert guards.guard_write(tool_input(path=committed, text="select 1")) == 0
    assert decision(capsys) == "ask"
    new = "supabase/migrations/29990101000001_not_yet_written.sql"
    assert guards.guard_write(tool_input(path=new, text="select 1")) == 0
    assert decision(capsys) is None


# -- shell and MCP guard ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "supabase db push --project-ref abc",
        "vercel --prod",
        "vercel deploy --prod",
        "git push origin main",
        "git reset --hard HEAD~1",
        'psql "$env:DATABASE_URL" -c "select 1"',
        "python -c \"print('drop table users')\"",
        "curl -u x:y https://api.twilio.com/2010-04-01/Accounts/x/Messages.json",
        "$env:SMS_PROVIDER_MODE='live'",
        "fly secrets set X=1",
        "Remove-Item -Recurse -Force backend",
    ],
)
def test_consequential_commands_ask(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    raw = json.dumps({"tool_name": "execute_pwsh", "tool_input": {"command": command}})
    assert guards.guard_shell(raw) == 0
    assert decision(capsys) == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "git status --short",
        "node run-db.mjs --tests",
        'Select-String -Pattern "drop table" -Path docs/*.md',
        "git grep -n truncate -- backend",
        "Remove-Item -Recurse -Force dist-check",
        "ruff check app",
    ],
)
def test_everyday_commands_pass(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    raw = json.dumps({"tool_name": "execute_pwsh", "tool_input": {"command": command}})
    assert guards.guard_shell(raw) == 0
    assert decision(capsys) is None


@pytest.mark.parametrize(
    "tool_id",
    [
        "github::push_files",
        "github::merge_pull_request",
        "bedrock-agentcore-mcp-server::execute_code",
    ],
)
def test_state_changing_mcp_calls_ask(tool_id: str, capsys: pytest.CaptureFixture[str]) -> None:
    raw = json.dumps(
        {"tool_name": "tool_call", "tool_input": {"tool_id": tool_id, "arguments": {}}}
    )
    assert guards.guard_shell(raw) == 0
    assert decision(capsys) == "ask"


def test_read_only_mcp_calls_pass(capsys: pytest.CaptureFixture[str]) -> None:
    raw = json.dumps({"tool_name": "tool_call", "tool_input": {"tool_id": "github::get_issue"}})
    assert guards.guard_shell(raw) == 0
    assert decision(capsys) is None


# -- security scan ---------------------------------------------------------------------------


def test_credential_findings_never_contain_the_value() -> None:
    findings = security.scan_text("backend/app/x.py", f'SID = "{FAKE_SID}"\n')
    assert [f.rule for f in findings] == ["credential-twilio-sid"]
    assert FAKE_SID not in json.dumps(findings[0].to_json())


def test_assigned_secret_is_flagged_in_source_but_not_in_tests() -> None:
    line = 'password = "correct-horse-battery-staple"\n'
    assert any(
        f.rule == "hardcoded-secret-assignment"
        for f in security.scan_text("backend/app/x.py", line)
    )
    assert not security.scan_text("backend/tests/unit/test_x.py", line)
    assert not security.scan_text("backend/app/x.py", 'password = os.environ["P"]\n')


def test_sensitive_value_in_log_call() -> None:
    bad = 'logger.info(f"sent to {phone}")\n'
    good = 'logger.info("sent", extra={"message_id": str(message_id)})\n'
    assert any(
        f.rule == "sensitive-value-in-log" for f in security.scan_text("backend/app/x.py", bad)
    )
    assert not security.scan_text("backend/app/x.py", good)


ROUTER = """
from fastapi import APIRouter
router = APIRouter(prefix="/things")

@router.get("/open")
async def open_thing() -> dict[str, str]:
    return {}

@router.get("/{thing_id}", response_model=None)
async def get_thing(thing_id: str, user: ActiveUserDep, service: ServiceDep):
    return await service.get(thing_id)

@router.post("")
async def make_thing(body: dict, user: ActiveUserDep, service: ServiceDep) -> dict[str, str]:
    return await service.make(user, body)
"""


def test_route_parsing_reads_prefix_methods_and_schemas() -> None:
    routes = {r.function: r for r in parse_routes("backend/app/modules/x/router.py", ROUTER)}
    assert routes["open_thing"].full_path == "/api/v1/things/open"
    assert routes["get_thing"].has_response_model
    assert routes["get_thing"].unused_principals == ["user"]
    assert routes["make_thing"].untyped_params == ["body"]
    assert routes["make_thing"].method == "POST"


def test_missing_authentication_and_unused_principal_are_reported() -> None:
    findings = security.check_routes("backend/app/modules/x/router.py", ROUTER)
    rules = {(f.rule, f.detail) for f in findings}
    assert ("route-without-authentication", "GET /api/v1/things/open") in rules
    assert ("authorisation-not-checked", "GET /api/v1/things/{thing_id}") in rules
    assert all("make" not in f.detail for f in findings)


def test_public_routes_are_exempt_by_allow_list() -> None:
    findings = security.check_routes("backend/app/modules/sms/webhook_router.py", ROUTER)
    assert findings == []


def test_webhook_router_without_verification_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    source = (
        'router = APIRouter(prefix="/webhooks")\n'
        '@router.post("/x")\nasync def hook(request: Request) -> dict[str, str]:\n'
        "    return await request.json()\n"
    )
    findings = security.check_webhooks("backend/app/modules/new/webhook_router.py", source)
    assert {f.rule for f in findings} == {
        "webhook-unverified",
        "webhook-parsed-before-verification",
    }
    verified = source + "\n# calls provider.validate_webhook(raw)\n"
    assert {
        f.rule
        for f in security.check_webhooks("backend/app/modules/new/webhook_router.py", verified)
    } == {"webhook-parsed-before-verification"}


# -- architecture ----------------------------------------------------------------------------


def test_cycle_detection() -> None:
    graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a"}, "e": set()}
    assert architecture._cycles(graph) == [["a", "b", "c"]]
    assert architecture._cycles({"a": {"b"}, "b": set()}) == []


def test_module_names() -> None:
    assert architecture.module_of("backend/app/modules/sms/service.py") == "app.modules.sms.service"
    assert architecture.package_of("app.modules.sms.service") == "app.modules.sms"
    assert architecture.package_of("app.core.config") == "app.core.config"


# -- reports ---------------------------------------------------------------------------------


def test_reports_round_trip_and_forget(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common, "REPORT_DIR", tmp_path)
    finding = Finding("security", "rule", "backend/app/a.py", "message", 3, "warn", "d")
    common.store_findings("security", [finding], scope=["backend/app/a.py"])
    assert common.load_findings() == [finding]
    common.store_findings("security", [], scope=["backend/app/a.py"])
    assert common.load_findings() == []
    common.store_findings("security", [finding])
    assert common.forget_file("backend/app/a.py") == 1
    assert common.load_findings() == []


def test_fingerprint_ignores_line_numbers() -> None:
    a = Finding("c", "r", "f.py", "m", 1, detail="x")
    b = Finding("c", "r", "f.py", "m", 99, detail="x")
    assert a.fingerprint == b.fingerprint


def test_summary_is_silent_without_findings_and_hides_info(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(hookcheck, "load_findings", lambda: [])
    assert hookcheck.summary() == 0
    assert capsys.readouterr().out == ""
    info = Finding("architecture", "complex-function", "backend/app/main.py", "m", severity="info")
    monkeypatch.setattr(hookcheck, "load_findings", lambda: [info])
    hookcheck.summary()
    assert capsys.readouterr().out == ""
    warn = Finding("security", "rule", "backend/app/main.py", "look here", severity="warn")
    monkeypatch.setattr(hookcheck, "load_findings", lambda: [warn])
    hookcheck.summary()
    assert "look here" in capsys.readouterr().out


def test_paths_are_found_in_any_json_shape() -> None:
    nested = json.dumps({"event": {"data": {"filePath": "backend/app/main.py"}}, "note": "no path"})
    assert common.paths_from_input(nested) == ["backend/app/main.py"]
    assert common.paths_from_input("not json") == []
    outside = json.dumps({"path": "C:/Windows/system32/x.dll"})
    assert common.paths_from_input(outside) == []
