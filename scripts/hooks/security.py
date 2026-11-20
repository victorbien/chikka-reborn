"""Security review of source files: secrets, sensitive values, webhooks, authentication, authorisation.

Pattern checks plus `ast` checks of FastAPI routers. Findings carry the rule, file and line only,
never the matched text, so a detected credential is not copied anywhere else.
These are heuristics. A clean result is not a security assessment (see docs/quality/security-audit-report.md).
"""

from __future__ import annotations

import re

from common import Finding, Result, read_text
from routes import parse_routes

# High confidence: the format itself identifies the credential. Checked in every text file.
CREDENTIAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "twilio-sid": re.compile(r"\bAC[0-9a-f]{32}\b"),
    "supabase-secret-key": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{10,}"),
    "stripe-live-key": re.compile(r"\bsk_live_[A-Za-z0-9]{10,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "database-url-with-password": re.compile(
        r"postgres(?:ql)?(?:\+\w+)?://[^:/\s@<>$]+:(?!\{|<|\$|password|pass@|p@|x@|\*)[^@\s<>]{6,}"
        r"@(?!localhost|127\.|\[|<|\$|host|db\.example|example)"
    ),
}

# Medium confidence: a secret-looking name assigned a long literal. Source code only.
ASSIGNED_SECRET = re.compile(
    r"""(?ix)\b(?:password|passwd|secret|api[_-]?key|auth[_-]?token|access[_-]?token|
    private[_-]?key|service[_-]?role[_-]?key)\w*\s*[:=]\s*["'][^"'\s${}<>]{16,}["']"""
)
BENIGN_LINE = re.compile(
    r"(?i)environ|getenv|settings\.|SecretStr|Field\(|example|placeholder|dummy|fake|"
    r"changeme|noqa|import\.meta\.env|\bz\.|schema|label|description|pattern"
)
PHONE_LITERAL = re.compile(r"""["']\+\d{9,15}["']""")
FICTIONAL_NUMBER = re.compile(r"\+1202555\d{4}|\+15550|\+4420794600")
LOG_CALL = re.compile(r"\blogger\.\w+\(")
SENSITIVE_IN_LOG = re.compile(
    r"\{[^}]*\b(password|token|secret|otp|body|message_text|phone|email|e164|authorization)\b[^}]*\}",
    re.IGNORECASE,
)

FRONTEND_PATTERNS: dict[str, re.Pattern[str]] = {
    "unsafe-html": re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*="),
    "dynamic-code": re.compile(r"\beval\(|new Function\("),
    "token-in-web-storage": re.compile(
        r"(?:localStorage|sessionStorage)\.setItem\([^)]*(?:token|password|secret)", re.IGNORECASE
    ),
    "secret-in-public-env": re.compile(
        r"VITE_\w*(?:SECRET|SERVICE_ROLE|PRIVATE|AUTH_TOKEN|API_KEY)", re.IGNORECASE
    ),
}

# Routes that are public on purpose. Everything else under backend/app must have a principal.
PUBLIC_ROUTE_FILES = {
    "backend/app/api/v1/health.py",
    "backend/app/modules/sms/webhook_router.py",
}
PUBLIC_ROUTE_FUNCTIONS = {
    "backend/app/modules/auth/router.py": {
        "register", "login", "refresh", "verify_email", "resend_verification",
        "reset_password", "reset_password_confirm",
    },
}  # fmt: skip
VERIFICATION_MARKERS = (
    "validate_webhook", "validate_webhook_signature", "verify_signature", "webhooks.handle(",
)  # fmt: skip

TEST_PATH = re.compile(r"(^|/)(tests?|e2e|__tests__)/|\.test\.|\.spec\.|\.e2e\.|conftest")
TEXT_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".mjs", ".sql", ".ps1", ".toml", ".yml", ".yaml", ".json",
    ".md", ".example", ".html", ".sh", ".cfg", ".ini", ".txt",
)  # fmt: skip


def scan_text(rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    is_test = bool(TEST_PATH.search(rel))
    is_doc = rel.endswith(".md")
    is_app_source = rel.startswith(("backend/app/", "frontend/src/")) and not is_test

    for number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in CREDENTIAL_PATTERNS.items():
            if pattern.search(line):
                findings.append(
                    Finding("security", f"credential-{name}", rel,
                            f"Looks like a {name.replace('-', ' ')}. Remove it, use an environment "
                            "variable, and rotate it if it was real.",
                            number, "error", detail=f"{name}:{number}")
                )  # fmt: skip
        if is_test or is_doc:
            continue
        if ASSIGNED_SECRET.search(line) and not BENIGN_LINE.search(line):
            findings.append(
                Finding("security", "hardcoded-secret-assignment", rel,
                        "A secret-like name is assigned a literal. Read it from the environment.",
                        number, "warn", detail=f"assign:{number}")
            )  # fmt: skip
        if is_app_source:
            if PHONE_LITERAL.search(line) and not FICTIONAL_NUMBER.search(line) and "#" not in line:
                findings.append(
                    Finding("security", "phone-number-literal", rel,
                            "A phone-number literal is in source. Use fictional test numbers only.",
                            number, "warn", detail=f"phone:{number}")
                )  # fmt: skip
            if LOG_CALL.search(line) and SENSITIVE_IN_LOG.search(line):
                findings.append(
                    Finding("security", "sensitive-value-in-log", rel,
                            "A log call interpolates a sensitive-looking value (token, body, "
                            "phone, email). Log ids and masked values only.",
                            number, "warn", detail=f"log:{number}")
                )  # fmt: skip
            if rel.startswith("frontend/src/"):
                for name, pattern in FRONTEND_PATTERNS.items():
                    if pattern.search(line):
                        findings.append(
                            Finding("security", f"frontend-{name}", rel,
                                    f"Frontend risk: {name.replace('-', ' ')}.",
                                    number, "warn", detail=f"{name}:{number}")
                        )  # fmt: skip
    return findings


def check_routes(rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    public_file = rel in PUBLIC_ROUTE_FILES
    public_functions = PUBLIC_ROUTE_FUNCTIONS.get(rel, set())
    for route in parse_routes(rel, text):
        label = f"{route.method} {route.full_path}"
        if (
            not route.principal_params
            and not public_file
            and route.function not in public_functions
        ):
            findings.append(
                Finding("security", "route-without-authentication", rel,
                        f"{label} has no CurrentUserDep/ActiveUserDep/AdminUserDep. Add one, or "
                        "list it as public in scripts/hooks/security.py with a reason.",
                        route.line, "error", detail=label)
            )  # fmt: skip
        elif route.unused_principals and not public_file:
            findings.append(
                Finding("security", "authorisation-not-checked", rel,
                        f"{label}: '{', '.join(route.unused_principals)}' authenticates but is "
                        "never used. Confirm ownership or role is checked in the service.",
                        route.line, "warn", detail=label)
            )  # fmt: skip
    return findings


def check_webhooks(rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if rel.startswith("backend/app/") and "webhook" in rel and parse_routes(rel, text):
        if not any(marker in text for marker in VERIFICATION_MARKERS):
            findings.append(
                Finding("security", "webhook-unverified", rel,
                        "Webhook routes without a signature check. Verify the raw body with the "
                        "provider's signing secret before any parsing or processing.",
                        severity="error", detail="routes")
            )  # fmt: skip
        if re.search(r"request\.(?:json|form)\(", text):
            findings.append(
                Finding("security", "webhook-parsed-before-verification", rel,
                        "Reads request.json()/form(). Verify the signature on the raw bytes first.",
                        severity="error", detail="parse")
            )  # fmt: skip
    if rel.startswith("backend/app/integrations/") and "def parse_inbound" in text:
        if "validate_webhook" not in text:
            findings.append(
                Finding("security", "provider-without-signature-validation", rel,
                        "A provider parses inbound webhooks but defines no validate_webhook.",
                        severity="error", detail="provider")
            )  # fmt: skip
    return findings


def run(paths: list[str]) -> Result:
    result = Result("security")
    for rel in paths:
        if not rel.endswith(TEXT_SUFFIXES) and not rel.rsplit("/", 1)[-1].startswith(".env"):
            continue
        if rel.endswith(("package-lock.json",)) or "/node_modules/" in rel:
            continue
        text = read_text(rel)
        result.findings += scan_text(rel, text)
        if rel.endswith(".py") and rel.startswith("backend/app/"):
            if "router" in rel or rel.startswith("backend/app/api/"):
                result.findings += check_routes(rel, text)
            result.findings += check_webhooks(rel, text)
    if not result.findings:
        result.notes.append("No security findings in the files checked (heuristic).")
    return result
