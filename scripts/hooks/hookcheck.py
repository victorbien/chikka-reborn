"""Entry point for the Kiro hook checks.  Usage:  python hookcheck.py <check> [options]

Checks: quality, tests, docs, security, architecture, all, summary, forget, guard-write, guard-shell.
Hook mode reads Kiro's JSON from stdin to find the file; manual mode takes --paths, --changed or --all.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import architecture  # noqa: E402
import docimpact  # noqa: E402
import guards  # noqa: E402
import quality  # noqa: E402
import security  # noqa: E402
import testcov  # noqa: E402
from common import (  # noqa: E402
    ROOT,
    Finding,
    Result,
    changed_files,
    forget_file,
    format_findings,
    load_baseline,
    load_findings,
    paths_from_input,
    read_stdin,
    save_baseline,
    store_findings,
    walk,
)

REPORT_CHECKS: dict[str, Callable[[list[str]], Result]] = {
    "quality": quality.run,
    "tests": testcov.run,
    "docs": docimpact.run,
    "security": security.run,
    "architecture": architecture.run,
}
BASELINED = {"tests", "docs", "security", "architecture"}


def is_reminder(finding: Finding) -> bool:
    """ "Review this document" reminders are about the change being made, so they are never accepted."""
    return finding.rule.endswith("-to-review")


def all_files() -> list[str]:
    files: list[str] = []
    for base, suffixes in (
        ("backend/app", (".py",)),
        ("backend/tests", (".py",)),
        ("frontend/src", (".ts", ".tsx")),
        ("supabase/migrations", (".sql",)),
        ("supabase/tests", (".sql",)),
        ("docs/product", (".md",)),
        ("scripts", (".py", ".ps1")),
    ):
        files += walk(base, suffixes)
    files += [
        p.relative_to(ROOT).as_posix()
        for pattern in (
            "backend/*.example",
            "backend/.env.example",
            "frontend/.env.example",
            "frontend/*.example",
        )
        for p in ROOT.glob(pattern)
    ]
    files += [f for f in ("docs/prd.md", "docs/frs.md", "docs/nfrs.md") if (ROOT / f).is_file()]
    return sorted(set(files))


def resolve_paths(args: argparse.Namespace, stdin: str) -> list[str]:
    if args.paths:
        return [p.replace("\\", "/") for p in args.paths]
    if args.all:
        return all_files()
    from_hook = paths_from_input(stdin)
    if from_hook and not args.changed:
        return from_hook
    return changed_files()


def run_report(check: str, paths: list[str], args: argparse.Namespace) -> list[Finding]:
    result = REPORT_CHECKS[check](paths)
    findings = result.findings
    if check in BASELINED:
        if args.update_baseline:
            count = save_baseline(check, [f for f in findings if not is_reminder(f)])
            print(f"{check}: baseline written with {count} accepted finding(s).")
            findings = []
        else:
            accepted = load_baseline(check)
            findings = [f for f in findings if is_reminder(f) or f.fingerprint not in accepted]
    if check == "architecture":
        store_findings(check, findings)
    elif check != "quality":
        store_findings(check, findings, scope=paths if not args.all else None)
    if args.print or args.all or sys.stdout.isatty():
        header = f"== {check}: {len(findings)} finding(s) in {len(paths)} file(s) checked"
        print(header)
        for line in format_findings(findings):
            print("  " + line)
        for note in result.notes if not findings else []:
            print("  " + note)
    return findings


def refresh_stored(args: argparse.Namespace) -> None:
    """Re-check files that have open findings, so fixed problems stop being reported."""
    by_check: dict[str, set[str]] = {}
    for finding in load_findings():
        if finding.check in ("tests", "docs", "security") and (ROOT / finding.file).is_file():
            by_check.setdefault(finding.check, set()).add(finding.file)
    quiet = argparse.Namespace(
        **{**vars(args), "print": False, "all": False, "update_baseline": False}
    )
    for check, files in by_check.items():
        run_report(check, sorted(files), quiet)
    if any(f.check == "architecture" for f in load_findings()):
        run_report("architecture", [], quiet)


def summary(args: argparse.Namespace | None = None) -> int:
    if args is not None:
        refresh_stored(args)
    findings = [
        f
        for f in load_findings()
        if f.severity != "info"
        and (f.file == "(project)" or (ROOT / f.file).is_file())
        and not docimpact.reminder_resolved(f)
    ]
    if not findings:
        return 0
    print(
        f"Automatic project checks (hooks) have {len(findings)} open finding(s). "
        "Fix those in files you are changing; mention others only if relevant. Refresh with "
        "scripts\\hooks\\run.ps1 all --all --print:"
    )
    for line in format_findings(findings, limit=25):
        print("  " + line)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="hookcheck")
    parser.add_argument(
        "check",
        choices=[*REPORT_CHECKS, "all", "summary", "forget", "guard-write", "guard-shell"],
    )
    parser.add_argument("--paths", nargs="*", default=[])
    parser.add_argument("--changed", action="store_true", help="use files changed in git")
    parser.add_argument("--all", action="store_true", help="check the whole project")
    parser.add_argument("--print", action="store_true", help="print findings to stdout")
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--strict", action="store_true", help="exit 1 when an error is found")
    args = parser.parse_args()
    stdin = read_stdin()

    if args.check == "guard-write":
        return guards.guard_write(stdin)
    if args.check == "guard-shell":
        return guards.guard_shell(stdin)
    if args.check == "summary":
        return summary(args)
    if args.check == "forget":
        removed = sum(forget_file(p) for p in paths_from_input(stdin, must_exist=False))
        print(f"forgot {removed} report(s)") if args.print else None
        return 0

    paths = resolve_paths(args, stdin)
    checks = list(REPORT_CHECKS) if args.check == "all" else [args.check]
    everything: list[Finding] = []
    for check in checks:
        everything += run_report(check, paths, args)
    if args.strict and any(f.severity == "error" for f in everything):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
