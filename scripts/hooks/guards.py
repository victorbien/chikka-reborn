"""PreToolUse guards: stop or ask before consequential actions.

Exit codes follow Kiro's hook rules: exit 2 blocks the tool call (stderr is shown to the agent),
exit 0 with a JSON `permissionDecision: "ask"` asks the person first, exit 0 with no output allows.
The guards never run, send or change anything themselves. They only read the tool request.

A pattern guard cannot see intent. It is a seat belt for the agent, not a security boundary:
a person with a terminal can do all of this directly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePosixPath

from common import is_tracked, iter_strings, parse_json, paths_from_input
from security import CREDENTIAL_PATTERNS, TEST_PATH

# -- file writes -------------------------------------------------------------------------------

ENV_FILE = re.compile(r"^(?:\.env(?:\..+)?|.+\.env)$", re.IGNORECASE)
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")
PROTECTED_PREFIXES = (
    ".kiro/hooks/", ".kiro/steering/", "scripts/hooks/",
)  # fmt: skip
PATH_KEYS = ("path", "file", "uri", "target")


def _ask(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


def _block(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def is_real_env_file(rel: str) -> bool:
    name = PurePosixPath(rel).name
    return bool(ENV_FILE.match(name)) and not name.lower().endswith(ENV_TEMPLATE_SUFFIXES)


def guard_write(raw: str) -> int:
    paths = paths_from_input(raw, must_exist=False)
    data = parse_json(raw)

    # 1. Credentials in the content being written (not in test fixtures).
    if data is not None and not any(TEST_PATH.search(p) for p in paths):
        for key, value in iter_strings(data):
            if any(word in key.lower() for word in PATH_KEYS) or len(value) < 12:
                continue
            for name, pattern in CREDENTIAL_PATTERNS.items():
                if pattern.search(value):
                    return _block(
                        f"Blocked by the secrets guard: the content looks like a {name.replace('-', ' ')}. "
                        "Read it from an environment variable and keep real values out of the repository. "
                        "If it was real, rotate it."
                    )

    for rel in paths:
        if is_real_env_file(rel):
            return _ask(
                f"'{rel}' holds environment values (possibly production credentials). "
                "Changing credentials needs human approval."
            )
        if re.match(r"^supabase/migrations/.+\.sql$", rel) and is_tracked(rel):
            return _ask(
                f"'{rel}' is already committed, so it may be applied. Applied migrations are never "
                "edited or deleted; add a new migration instead."
            )
        if rel.startswith(PROTECTED_PREFIXES):
            return _ask(
                f"'{rel}' defines project rules or automation. Weakening hooks or steering needs "
                "human approval."
            )
    return 0


# -- shell and MCP calls -----------------------------------------------------------------------

READ_ONLY_START = re.compile(
    r"^\s*(?:git\s+(?:grep|log|diff|show|status|ls-files)|select-string|get-content|get-childitem|"
    r"rg|grep|findstr|cat|type|ls|dir)\b",
    re.IGNORECASE,
)
SAFE_DELETE_TARGETS = re.compile(
    r"(?:node_modules|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|htmlcov|dist(?:-\w+)?|"
    r"coverage|e2e-results|hook-reports|\.coverage)\b",
    re.IGNORECASE,
)

SHELL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("destructive database operation", re.compile(
        r"\bdrop\s+(?:table|schema|database|column|policy)\b|\btruncate\b|\bdelete\s+from\s+\w|"
        r"\bsupabase\s+db\s+(?:reset|push)\b|\bdb\s+reset\b|alembic\s+downgrade|reset_dev_data|"
        r"\bpsql\b|\bpg_restore\b", re.I)),
    ("production deployment or release", re.compile(
        r"\bvercel(?:\.cmd)?\s+(?:deploy|--prod|promote|rollback|redeploy)|"
        r"\bdocker\s+(?:push|compose\s+up\s+--build.*prod)|\bfly(?:ctl)?\s+(?:deploy|releases)|"
        r"\brailway\s+(?:up|deploy|rollback)|\brender\s+deploy|\bgit\s+push\b|\bgh\s+(?:pr\s+merge|release)|"
        r"\bsupabase\s+(?:config\s+push|link|functions\s+deploy)|\bnpm\s+publish", re.I)),
    ("live SMS or provider activation", re.compile(
        r"api\.twilio\.com|\btwilio\s+api\b|sms_provider_mode\s*=\s*['\"]?live|"
        r"sms_live_confirmed\s*=\s*['\"]?true|/admin/sms/providers/[^\s]+/activate", re.I)),
    ("change to production credentials or secrets", re.compile(
        r"\bvercel(?:\.cmd)?\s+env\s+(?:add|rm|pull)|\bfly(?:ctl)?\s+secrets|\brailway\s+variables|"
        r"\bsupabase\s+secrets|\bgh\s+secret|\baws\s+(?:iam|configure|secretsmanager|ssm|sts)|"
        r"\bsetx?\s+\w*(?:token|secret|key|password)\w*\s", re.I)),
    ("financial transaction", re.compile(
        r"\bstripe\b|\bpaypal\b|\bbraintree\b|/admin/credits/adjustments|/payments?\b|\bbilling\b", re.I)),
    ("hard-to-reverse git operation", re.compile(
        r"\bgit\s+(?:reset\s+--hard|clean\s+-\w*f|push\s+.*--force|branch\s+-D|checkout\s+--\s|restore\s+\.)", re.I)),
]  # fmt: skip
FORCE_DELETE = re.compile(
    r"\brm\s+-\w*r\w*f|\bremove-item\b[^|;]*-recurse|\bremove-item\b[^|;]*-force[^|;]*-recurse|\brmdir\s+/s|\bdel\s+/s",
    re.I,
)
MCP_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("GitHub write operation", re.compile(
        r"github::(?:push_files|create_or_update_file|merge_pull_request|create_pull_request|"
        r"update_pull_request_branch|create_repository|fork_repository|create_branch|update_issue|"
        r"create_issue|add_issue_comment|create_pull_request_review)\b")),
    ("AWS resource change or code execution", re.compile(
        r"bedrock-agentcore-mcp-server::(?:create_|delete_|update_|put_|stop_|invoke_agent_runtime|"
        r"gateway_(?:create|delete|update|target_)|policy_|identity_(?:create|delete|update|put|set)|"
        r"memory_(?:create|delete|update|batch|start)|execute_code|execute_command|install_packages|"
        r"upload_file|browser_)")),
]  # fmt: skip


def guard_shell(raw: str) -> int:
    data = parse_json(raw)
    text = "\n".join(v for _, v in iter_strings(data)) if data is not None else raw
    reasons: list[str] = []

    for name, pattern in MCP_RULES:
        if pattern.search(text):
            reasons.append(name)

    pairs = list(iter_strings(data)) if data is not None else []
    command = next((v for k, v in pairs if k == "command"), text).strip()
    read_only = bool(READ_ONLY_START.match(command)) and not re.search(
        r"\|\s*(?:psql|sh|bash|iex|invoke-expression)|\bpsql\b|\bsupabase\b|\bpython\b|\bnode\b",
        command,
        re.I,
    )
    if not read_only:
        for name, pattern in SHELL_RULES:
            if pattern.search(text):
                reasons.append(name)
        if FORCE_DELETE.search(text) and not SAFE_DELETE_TARGETS.search(text):
            reasons.append("recursive or forced deletion")

    if reasons:
        unique = ", ".join(dict.fromkeys(reasons))
        return _ask(
            f"This looks like: {unique}. These actions can change production, cost money, send real "
            "messages or lose data, so a person must approve them (project safety rules)."
        )
    return 0
