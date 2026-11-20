"""Code quality: formatting, lint and type errors for the files that changed.

Backend (from backend/): ruff check, ruff format --check, mypy (project, strict as configured).
Frontend (from frontend/): eslint, prettier --check, tsc --noEmit (project).
Only reports; never rewrites a file. Use `ruff format` / `prettier --write` yourself.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

from common import ROOT, Finding, Result, store_findings, to_rel

BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
TIMEOUT = 170

_RUFF = re.compile(r"^(?P<file>.+?):(?P<line>\d+):\d+: (?P<code>\S+) (?P<msg>.*)$")
_MYPY = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<level>error|warning): (?P<msg>.*)$")
_TSC = re.compile(r"^(?P<file>.+?)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.*)$")


def _run(cmd: list[str], cwd: str) -> tuple[int, str] | None:
    try:
        done = subprocess.run(  # noqa: S603
            cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def _unavailable(tool: str, why: str) -> Finding:
    return Finding(
        "quality", "tool-unavailable", "(project)", f"{tool} could not run: {why}",
        severity="info",
    )  # fmt: skip


def _backend_rel(name: str) -> str:
    return "backend/" + name.replace("\\", "/").removeprefix("./")


def backend_checks(files: list[str]) -> tuple[list[Finding], list[Finding]]:
    """Returns (per-file findings, project-wide type findings)."""
    local: list[Finding] = []
    types: list[Finding] = []
    rel = [f.removeprefix("backend/") for f in files]
    py = sys.executable

    ran = _run([py, "-m", "ruff", "check", "--output-format", "concise", *rel], str(BACKEND))
    if ran is None or "No module named ruff" in ran[1]:
        local.append(_unavailable("ruff", "not installed in the backend virtualenv"))
    else:
        for line in ran[1].splitlines():
            match = _RUFF.match(line.strip())
            if match:
                local.append(
                    Finding(
                        "quality", f"ruff-{match['code']}", _backend_rel(match["file"]),
                        match["msg"], int(match["line"]), "error",
                    )
                )  # fmt: skip

    ran = _run([py, "-m", "ruff", "format", "--check", *rel], str(BACKEND))
    if ran is not None and ran[0] != 0 and "No module named ruff" not in ran[1]:
        for line in ran[1].splitlines():
            if line.startswith("Would reformat: "):
                name = _backend_rel(line.removeprefix("Would reformat: ").strip())
                local.append(
                    Finding("quality", "ruff-format", name,
                            "Not formatted. Run: ruff format " + name.removeprefix("backend/"),
                            severity="warn")
                )  # fmt: skip

    if any(f.startswith("backend/app/") for f in files):
        ran = _run([py, "-m", "mypy", "app"], str(BACKEND))
        if ran is None or "No module named mypy" in ran[1]:
            types.append(_unavailable("mypy", "not installed or timed out"))
        else:
            for line in ran[1].splitlines():
                match = _MYPY.match(line.strip())
                if match and match["level"] == "error":
                    types.append(
                        Finding("types-mypy", "mypy", _backend_rel(match["file"]),
                                match["msg"], int(match["line"]), "error")
                    )  # fmt: skip
    return local, types


def frontend_checks(files: list[str]) -> tuple[list[Finding], list[Finding]]:
    local: list[Finding] = []
    types: list[Finding] = []
    node = shutil.which("node")
    rel = [f.removeprefix("frontend/") for f in files]
    if node is None or not (FRONTEND / "node_modules").is_dir():
        return [_unavailable("frontend tools", "node or frontend/node_modules is missing")], []

    eslint = str(FRONTEND / "node_modules/eslint/bin/eslint.js")
    ran = _run([node, eslint, "-f", "json", *rel], str(FRONTEND))
    if ran is not None:
        try:
            payload = json.loads(ran[1][ran[1].index("[") :])
        except ValueError:
            payload = []
        for entry in payload if isinstance(payload, list) else []:
            name = to_rel(str(entry.get("filePath", ""))) or str(entry.get("filePath", ""))
            for msg in entry.get("messages", []):
                local.append(
                    Finding("quality", f"eslint-{msg.get('ruleId') or 'parse'}", name,
                            str(msg.get("message", "")), int(msg.get("line") or 0),
                            "error" if msg.get("severity") == 2 else "warn")
                )  # fmt: skip

    prettier = str(FRONTEND / "node_modules/prettier/bin/prettier.cjs")
    ran = _run([node, prettier, "--check", *rel], str(FRONTEND))
    if ran is not None and ran[0] != 0:
        for line in ran[1].splitlines():
            if line.startswith("[warn] ") and "Code style issues" not in line:
                name = "frontend/" + line.removeprefix("[warn] ").strip().replace("\\", "/")
                local.append(
                    Finding("quality", "prettier", name,
                            "Not formatted. Run: prettier --write " + name.removeprefix("frontend/"),
                            severity="warn")
                )  # fmt: skip

    tsc = str(FRONTEND / "node_modules/typescript/bin/tsc")
    ran = _run([node, tsc, "--noEmit", "--pretty", "false"], str(FRONTEND))
    if ran is not None and ran[0] != 0:
        for line in ran[1].splitlines():
            match = _TSC.match(line.strip())
            if match:
                types.append(
                    Finding("types-tsc", match["code"], "frontend/" + match["file"].replace("\\", "/"),
                            match["msg"], int(match["line"]), "error")
                )  # fmt: skip
    return local, types


def run(paths: list[str]) -> Result:
    result = Result("quality")
    backend = [p for p in paths if p.startswith("backend/") and p.endswith(".py")]
    frontend = [
        p for p in paths
        if p.startswith("frontend/src/") and p.endswith((".ts", ".tsx"))
    ]  # fmt: skip
    if not backend and not frontend:
        result.notes.append("No Python or TypeScript source files to check.")
        return result

    if backend:
        local, types = backend_checks(backend)
        store_findings("quality", [f for f in local if f.file in backend], scope=backend)
        if any(f.file == "(project)" for f in local):
            result.findings += [f for f in local if f.file == "(project)"]
        result.findings += [f for f in local if f.file != "(project)"]
        if any(p.startswith("backend/app/") for p in backend):
            store_findings("types-mypy", types)
            result.findings += types
    if frontend:
        local, types = frontend_checks(frontend)
        store_findings("quality", [f for f in local if f.file in frontend], scope=frontend)
        result.findings += local
        store_findings("types-tsc", types)
        result.findings += types
    return result
