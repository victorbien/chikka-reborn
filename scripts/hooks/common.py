"""Shared helpers for the Kiro hook checks. Standard library only.

Kiro passes a JSON document on stdin to command hooks, but its field names are not documented,
so nothing here depends on a particular shape: every string value is inspected and anything
that looks like a project file is used. When no file can be found, the checks fall back to the
files git reports as changed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / ".kiro" / "hook-reports"
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "__pycache__", "dist", "dist-check", "dist-verify",
    "htmlcov", ".mypy_cache", ".ruff_cache", ".pytest_cache", "coverage", "e2e-results",
}  # fmt: skip

SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    check: str
    rule: str
    file: str
    message: str
    line: int = 0
    severity: str = "warn"
    detail: str = ""

    @property
    def fingerprint(self) -> str:
        """Stable across line shifts, so baselines survive unrelated edits."""
        return f"{self.rule}|{self.file}|{self.detail or self.message}"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Result:
    check: str
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# -- stdin and paths ---------------------------------------------------------------------------


def read_stdin() -> str:
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return ""
        return sys.stdin.read()
    except (OSError, ValueError):
        return ""


def iter_strings(node: Any, key: str = "") -> Iterator[tuple[str, str]]:
    """Every (key, string value) pair in a JSON-like structure."""
    if isinstance(node, str):
        yield key, node
    elif isinstance(node, dict):
        for child_key, value in node.items():
            yield from iter_strings(value, str(child_key))
    elif isinstance(node, list):
        for item in node:
            yield from iter_strings(item, key)


def parse_json(raw: str) -> Any:
    try:
        return json.loads(raw) if raw.strip() else None
    except ValueError:
        return None


def to_rel(path_text: str) -> str | None:
    """A repository-relative POSIX path, or None when the text is not inside the project."""
    text = path_text.strip().strip("\"'")
    if not text or "\n" in text or len(text) > 400:
        return None
    candidate = Path(text)
    try:
        if candidate.is_absolute():
            return candidate.resolve().relative_to(ROOT).as_posix()
        if text.startswith("file:"):
            return None
        return (ROOT / candidate).resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return None


def paths_from_input(raw: str, *, must_exist: bool = True) -> list[str]:
    data = parse_json(raw)
    if data is None:
        return []
    found: list[str] = []
    for key, value in iter_strings(data):
        lowered = key.lower()
        if not any(word in lowered for word in ("path", "file", "uri", "target")):
            continue
        rel = to_rel(value)
        if rel is None or rel in found:
            continue
        if must_exist and not (ROOT / rel).is_file():
            continue
        found.append(rel)
    return found


def git(*args: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout


def changed_files() -> list[str]:
    """Modified, added and untracked files (untracked directories expanded)."""
    files: list[str] = []
    for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
        if len(line) < 4:
            continue
        name = line[3:].split(" -> ")[-1].strip().strip('"')
        if (ROOT / name).is_file() and not any(part in SKIP_DIRS for part in Path(name).parts):
            files.append(name)
    return files


def is_tracked(rel: str) -> bool:
    return bool(git("ls-files", "--", rel).strip())


def read_text(rel: str) -> str:
    try:
        return (ROOT / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def walk(base: str, suffixes: tuple[str, ...]) -> list[str]:
    root = ROOT / base
    if not root.is_dir():
        return []
    out: list[str] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in suffixes:
            if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                out.append(path.relative_to(ROOT).as_posix())
    return sorted(out)


# -- reports and baselines ---------------------------------------------------------------------


def _slug(rel: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", rel)


def load_baseline(check: str) -> set[str]:
    data = (
        parse_json((BASELINE_DIR / f"{check}.json").read_text(encoding="utf-8"))
        if (BASELINE_DIR / f"{check}.json").is_file()
        else None
    )
    return set(data.get("accepted", [])) if isinstance(data, dict) else set()


def save_baseline(check: str, findings: list[Finding]) -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    accepted = sorted({f.fingerprint for f in findings})
    payload = {
        "check": check,
        "note": "Findings accepted as existing. Regenerate with --update-baseline after review.",
        "accepted": accepted,
    }
    (BASELINE_DIR / f"{check}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return len(accepted)


def store_findings(check: str, findings: list[Finding], *, scope: list[str] | None = None) -> None:
    """Replace stored findings: for the files in `scope`, or for the whole check when None.

    Reports hold rule names, paths, line numbers and messages. They never hold matched text,
    so a detected secret is not copied into a second file.
    """
    folder = REPORT_DIR / check
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.json"):
        if scope is None:
            old.unlink(missing_ok=True)
        elif any(old.name == f"{_slug(rel)}.json" for rel in scope):
            old.unlink(missing_ok=True)
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.file, []).append(finding)
    for rel, items in grouped.items():
        (folder / f"{_slug(rel)}.json").write_text(
            json.dumps([i.to_json() for i in items], indent=1), encoding="utf-8"
        )


def load_findings() -> list[Finding]:
    findings: list[Finding] = []
    if not REPORT_DIR.is_dir():
        return findings
    for path in REPORT_DIR.glob("*/*.json"):
        data = parse_json(path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, list):
            continue
        for item in data:
            try:
                findings.append(Finding(**item))
            except TypeError:
                continue
    return findings


def forget_file(rel: str) -> int:
    removed = 0
    if REPORT_DIR.is_dir():
        for path in REPORT_DIR.glob(f"*/{_slug(rel)}.json"):
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def format_findings(findings: list[Finding], limit: int = 40) -> list[str]:
    ordered = sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.file, f.line))
    lines = [
        f"[{f.severity}] {f.check}/{f.rule} {f.file}{':' + str(f.line) if f.line else ''}: "
        f"{f.message}"
        for f in ordered[:limit]
    ]
    if len(ordered) > limit:
        lines.append(f"... and {len(ordered) - limit} more")
    return lines
