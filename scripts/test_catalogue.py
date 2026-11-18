"""Builds docs/quality/test-case-catalogue.md from the result files of the last full run.

Inputs (all produced by the commands in docs/quality/test-report.md):
  backend/junit-backend.xml            pytest --junitxml
  frontend/coverage/vitest-results.json   vitest --reporter=json
  frontend/e2e-results/results.json    playwright (json reporter)
  supabase/tests/database/*.sql        listed only; the runner reports pass/fail per file

The catalogue states what each test case checks and the status it had in that run. Nothing is
invented: a test that did not appear in a result file does not appear here.
Run with the backend virtualenv:  backend\\.venv\\Scripts\\python.exe scripts\\test_catalogue.py
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "quality" / "test-case-catalogue.md"

# File -> requirement area, so the catalogue reads by feature as well as by suite.
AREAS = {
    "test_registration_and_verification": "Authentication",
    "test_sessions_and_passwords": "Authentication",
    "test_security": "Authentication",
    "test_security_asymmetric": "Authentication",
    "test_profiles": "Profiles",
    "test_profile_helpers": "Profiles",
    "test_phone_and_deletion": "Profiles",
    "test_contacts": "Contacts",
    "test_chat": "Conversations and messaging",
    "test_sms": "SMS",
    "test_sms_live": "SMS",
    "test_sms_helpers": "SMS",
    "test_sms_providers": "SMS",
    "test_ai": "AI",
    "test_ai_api": "AI",
    "test_ai_providers": "AI",
    "test_ai_service": "AI",
    "test_notifications": "Notifications",
    "test_notification_rules": "Notifications",
    "test_credits": "Credits",
    "test_credit_ledger_and_dispatcher": "Credits",
    "test_admin": "Administration",
    "test_admin_access": "Administration",
    "test_failure_paths": "Failure handling",
}


def status_icon(status: str) -> str:
    return {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP"}.get(status, status.upper())


def escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def backend_cases() -> list[tuple[str, str, str, str]]:
    path = ROOT / "backend" / "junit-backend.xml"
    cases = []
    # The JUnit file is written by our own pytest run on this machine, not received from outside.
    for case in ET.parse(path).getroot().iter("testcase"):  # noqa: S314
        classname = case.get("classname", "")
        parts = classname.split(".")  # tests.flows.test_sms
        layer = parts[1] if len(parts) > 1 else "tests"
        module = parts[-1]
        status = "passed"
        if case.find("failure") is not None or case.find("error") is not None:
            status = "failed"
        elif case.find("skipped") is not None:
            status = "skipped"
        area = AREAS.get(module, "Platform and infrastructure")
        cases.append((f"{layer}/{module}", area, case.get("name", ""), status))
    return cases


def frontend_cases() -> list[tuple[str, str, str, str]]:
    path = ROOT / "frontend" / "coverage" / "vitest-results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for file in data["testResults"]:
        name = re.sub(r"^.*?frontend[\\/]src[\\/]", "", file["name"].replace("\\", "/"))
        name = name.replace("/", "/")
        for test in file["assertionResults"]:
            status = {"passed": "passed", "failed": "failed"}.get(test["status"], "skipped")
            area = name.split("/")[1] if name.startswith("features/") else name.split("/")[0]
            cases.append((name, area, test["fullName"], status))
    return cases


def e2e_cases() -> list[tuple[str, str, str, str]]:
    path = ROOT / "frontend" / "e2e-results" / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases: list[tuple[str, str, str, str]] = []

    def walk(suite: dict, trail: list[str], file: str) -> None:
        file = suite.get("file", file) or file
        titles = trail + ([suite["title"]] if suite.get("title") and suite["title"] != file else [])
        for spec in suite.get("specs", []):
            result = spec["tests"][0]["results"][-1] if spec["tests"][0]["results"] else {}
            status = result.get("status", "skipped")
            status = (
                "passed" if status == "passed" else "skipped" if status == "skipped" else "failed"
            )
            cases.append(
                (file, file.removesuffix(".e2e.ts"), " > ".join([*titles, spec["title"]]), status)
            )
        for child in suite.get("suites", []):
            walk(child, titles, file)

    for suite in data["suites"]:
        walk(suite, [], suite.get("file", ""))
    return cases


def section(title: str, cases: list[tuple[str, str, str, str]], by_area: bool) -> list[str]:
    lines = [f"## {title}", ""]
    counts: dict[str, int] = defaultdict(int)
    for *_, status in cases:
        counts[status] += 1
    lines.append(
        f"{len(cases)} cases: {counts['passed']} passed, {counts['failed']} failed, "
        f"{counts['skipped']} skipped."
    )
    lines.append("")
    groups: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for file, area, name, status in cases:
        groups[area if by_area else file].append((file, name, status))
    for key in sorted(groups):
        lines += [
            f"### {key} ({len(groups[key])})",
            "",
            "| Status | File | Test case |",
            "|---|---|---|",
        ]
        for file, name, status in groups[key]:
            lines.append(f"| {status_icon(status)} | `{file}` | {escape(name)} |")
        lines.append("")
    return lines


def main() -> int:
    backend, frontend, e2e = backend_cases(), frontend_cases(), e2e_cases()
    sql_files = sorted((ROOT / "supabase" / "tests" / "database").glob("*.sql"))
    lines = [
        "# Test case catalogue",
        "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M} by `scripts/test_catalogue.py` "
        "from the result files of the last "
        "full run. Do not edit by hand: regenerate it. Totals and coverage are in "
        "[test-report.md](test-report.md).",
        "",
        "| Suite | Cases | Passed | Failed | Skipped |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, cases in (
        ("Backend (pytest)", backend),
        ("Frontend (Vitest)", frontend),
        ("Browser (Playwright)", e2e),
    ):
        c = defaultdict(int)
        for *_, status in cases:
            c[status] += 1
        lines.append(f"| {label} | {len(cases)} | {c['passed']} | {c['failed']} | {c['skipped']} |")
    lines += [
        "",
        "Database SQL suites (run by `npm test` in `supabase/tools`, "
        "which reports ok/fail per file):",
        "",
    ]
    lines += [f"- `{f.name}`" for f in sql_files]
    lines.append("")
    lines += section("Backend (pytest), by requirement area", backend, by_area=True)
    lines += section("Frontend (Vitest), by feature", frontend, by_area=True)
    lines += section("Browser end-to-end (Playwright), by spec", e2e, by_area=False)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(backend)} backend, {len(frontend)} frontend, {len(e2e)} e2e cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
