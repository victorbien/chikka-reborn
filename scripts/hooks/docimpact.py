"""Which documents a change affects. It lists documents; it never edits them.

* API: router/schema files -> docs/api/*.md and docs/api-design.md, plus routes missing from them.
* Database: migrations -> docs/database/*.md, plus new tables, policies and the migration list.
* Requirements: product docs -> acceptance criteria, test catalogue and traceability, plus the
  requirement IDs in the diff that those documents do not mention.
"""

from __future__ import annotations

import re

from common import ROOT, Finding, Result, git, is_tracked, read_text
from routes import parse_routes

API_DOC_BY_MODULE = {
    "admin": "docs/api/administration-api.md",
    "ai": "docs/api/ai-api.md",
    "auth": "docs/api/authentication-api.md",
    "profiles": "docs/api/authentication-api.md",
    "chat": "docs/api/messaging-api.md",
    "contacts": "docs/api/contacts-api.md",
    "credits": "docs/api/credits-api.md",
    "notifications": "docs/api/notifications-api.md",
    "sms": "docs/api/sms-api.md",
}
API_MODULE = re.compile(r"^backend/app/modules/(?P<module>[^/]+)/[^/]+\.py$")
API_FILE = re.compile(r"^backend/app/modules/[^/]+/(?:[a-z_]*router|schemas)\.py$")
REQUIREMENT_ID = re.compile(r"\b(?:FR|NFR|AC)-[A-Z0-9]+-\d{2,4}\b")
QUALITY_DOCS = (
    "docs/quality/acceptance-criteria.md",
    "docs/quality/test-case-catalogue.md",
    "docs/database/requirements-traceability.md",
)


def _normalise(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path).rstrip("/").lower()


def _existing(*docs: str) -> list[str]:
    return [d for d in docs if (ROOT / d).is_file()]


def api_impact(rel: str) -> list[Finding]:
    findings: list[Finding] = []
    module = API_MODULE.match(rel)
    targets = _existing(
        API_DOC_BY_MODULE.get(module["module"], "docs/api/api-overview.md") if module else "",
        "docs/api-design.md",
    )
    if "webhook" in rel:
        targets = _existing("docs/api/sms-api.md", "docs/api-design.md")
    is_schema = rel.endswith("schemas.py")
    findings.append(
        Finding("docs", "api-docs-to-review", rel,
                ("Request/response schemas changed: " if is_schema else "Routes changed: ")
                + "review " + ", ".join(targets or ["docs/api/"]) + ".",
                severity="info", detail=",".join(targets))
    )  # fmt: skip
    if is_schema:
        return findings
    # Any API document may describe a route (admin SMS routes live in the administration guide).
    api_docs = [str(p.relative_to(ROOT).as_posix()) for p in (ROOT / "docs/api").glob("*.md")]
    corpus = "\n".join(_normalise(read_text(t)) for t in [*targets, *api_docs])
    for route in parse_routes(rel):
        shown = _normalise(route.path)
        if shown not in corpus and _normalise(route.full_path) not in corpus:
            label = f"{route.method} {route.full_path}"
            findings.append(
                Finding("docs", "endpoint-undocumented", rel,
                        f"{label} does not appear in {', '.join(targets) or 'docs/api'}.",
                        route.line, "warn", detail=label)
            )  # fmt: skip
    return findings


def database_impact(rel: str) -> list[Finding]:
    text = read_text(rel).lower()
    stem = rel.rsplit("/", 1)[-1].removesuffix(".sql")
    findings = [
        Finding("docs", "db-docs-to-review", rel,
                "Schema changed: review docs/database-design.md and docs/database/"
                "(database-schema.md, entity-relationships.md).",
                severity="info")
    ]  # fmt: skip
    if stem not in read_text("docs/database/database-migrations.md"):
        findings.append(
            Finding("docs", "migration-not-listed", rel,
                    f"Add '{stem}' to docs/database/database-migrations.md.",
                    severity="warn", detail=stem)
        )  # fmt: skip
    schema_docs = read_text("docs/database/schema-reference.md") + read_text(
        "docs/database/database-schema.md"
    )
    for table in sorted(
        set(re.findall(r"create table (?:if not exists )?(?:public\.)?(\w+)", text))
    ):
        if table not in schema_docs.lower():
            findings.append(
                Finding("docs", "table-undocumented", rel,
                        f"Table '{table}' is not in docs/database/. Regenerate the reference: "
                        "cd supabase/tools; npm run schema:docs, and describe it in database-schema.md.",
                        severity="warn", detail=table)
            )  # fmt: skip
    if re.search(r"create policy|enable row level security|\bgrant\b|\brevoke\b", text):
        findings.append(
            Finding("docs", "rls-docs-to-review", rel,
                    "Policies or grants changed: update docs/database/row-level-security.md and "
                    "add allowed/denied tests under supabase/tests/database/.",
                    severity="warn", detail="rls")
        )  # fmt: skip
    return findings


def requirements_impact(rel: str) -> list[Finding]:
    findings = [
        Finding("docs", "requirements-docs-to-review", rel,
                "Requirements changed: review " + ", ".join(_existing(*QUALITY_DOCS))
                + " and any related user journey in docs/design/user-journeys.md.",
                severity="info")
    ]  # fmt: skip
    if not is_tracked(rel):
        return findings
    diff = git("diff", "HEAD", "-U0", "--", rel)
    changed = {
        i for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))
        for i in REQUIREMENT_ID.findall(line)
    }  # fmt: skip
    corpus = "\n".join(read_text(d) for d in QUALITY_DOCS)
    for requirement in sorted(changed):
        if requirement not in corpus:
            findings.append(
                Finding("docs", "requirement-without-acceptance", rel,
                        f"{requirement} was added or changed but is not in the acceptance "
                        "criteria, test catalogue or traceability documents.",
                        severity="warn", detail=requirement)
            )  # fmt: skip
    return findings


def run(paths: list[str]) -> Result:
    result = Result("docs")
    for rel in paths:
        if API_FILE.match(rel) or rel.endswith("webhook_router.py"):
            result.findings += api_impact(rel)
        elif rel.startswith("supabase/migrations/") and rel.endswith(".sql"):
            result.findings += database_impact(rel)
        elif rel in {"docs/prd.md", "docs/frs.md", "docs/nfrs.md"} or rel.startswith(
            (
                "docs/product/frs/",
                "docs/product/functional-requirements",
                "docs/product/non-functional",
            )
        ):
            result.findings += requirements_impact(rel)
    if not result.findings:
        result.notes.append("No documentation impact detected for the files checked.")
    return result


def reminder_resolved(finding: Finding) -> bool:
    """A "review this document" reminder is cleared once a related document is newer than the file."""
    source = ROOT / finding.file
    if not source.is_file() or not finding.rule.endswith("-to-review"):
        return False
    if finding.rule == "api-docs-to-review":
        related = [d for d in finding.detail.split(",") if d]
    elif finding.rule == "requirements-docs-to-review":
        related = list(QUALITY_DOCS)
    else:
        related = ["docs/database-design.md"] + [
            p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/database").glob("*.md")
        ]
    newest = (
        max((ROOT / d).stat().st_mtime for d in related if (ROOT / d).is_file()) if related else 0
    )
    return newest >= source.stat().st_mtime
