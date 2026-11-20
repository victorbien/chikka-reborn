"""Test coverage hints for new or changed services, API endpoints and frontend features.

These are reference checks, not coverage measurement: they ask "does any test mention this
module, route or component?". Real line coverage comes from `pytest --cov` and `vitest --coverage`.
"""

from __future__ import annotations

import ast
import re
from functools import cache

from common import Finding, Result, read_text, walk
from routes import parse_routes

SERVICE = re.compile(
    r"^backend/app/(?:modules/(?P<module>[^/]+)/[^/]*service[^/]*\.py|services/(?P<plain>[^/]+)\.py)$"
)
ROUTER = re.compile(r"^backend/app/(?:modules/(?P<module>[^/]+)/[^/]*router[^/]*\.py)$")
FEATURE = re.compile(r"^frontend/src/features/(?P<feature>[^/]+)/(?P<rest>.+)\.(?P<ext>tsx?)$")

TEST_PLAN = (
    "Cover (testing.md): authorisation denied, invalid input, duplicate/idempotent request, "
    "status transitions and each acceptance criterion; use fakes for SMS, AI and email."
)


@cache
def backend_tests() -> dict[str, str]:
    return {rel: read_text(rel) for rel in walk("backend/tests", (".py",))}


@cache
def frontend_tests() -> dict[str, str]:
    return {
        rel: read_text(rel)
        for rel in walk("frontend/src", (".ts", ".tsx"))
        if re.search(r"\.test\.tsx?$", rel)
    }


def _public_names(rel: str) -> list[str]:
    try:
        tree = ast.parse(read_text(rel))
    except SyntaxError:
        return []
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            names.append(node.name)
            names += [
                f"{n.name}"
                for n in node.body
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                and not n.name.startswith("_")
            ]
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith(
            "_"
        ):
            names.append(node.name)
    return names


def check_service(rel: str, module: str) -> list[Finding]:
    tests = backend_tests()
    needles = (f"app.modules.{module}", f"modules/{module}", f"modules\\{module}")
    referencing = {
        t: text
        for t, text in tests.items()
        if any(n in text for n in needles) or f"test_{module}" in t
    }
    unit = [t for t in referencing if "/tests/unit/" in t or t.startswith("backend/tests/unit/")]
    if not referencing:
        return [
            Finding("tests", "service-no-tests", rel,
                    f"No test references module '{module}'. Add backend/tests/unit/test_{module.removesuffix('_service')}"
                    f"_service.py (business rules) and a flow test for its endpoints. {TEST_PLAN}",
                    severity="error", detail=module)
        ]  # fmt: skip
    findings: list[Finding] = []
    if not unit:
        findings.append(
            Finding("tests", "service-no-unit-tests", rel,
                    f"Only flow/integration tests reference '{module}'. Business rules (credits, "
                    "status transitions, validation) need unit tests too.",
                    severity="warn", detail=module)
        )  # fmt: skip
    blob = "\n".join(referencing.values())
    missing = [n for n in _public_names(rel) if not re.search(rf"\b{re.escape(n)}\b", blob)]
    if missing:
        findings.append(
            Finding("tests", "service-names-unreferenced", rel,
                    "Not named in any related test (may still be covered through the API): "
                    + ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else ""),
                    severity="info", detail=",".join(sorted(missing)))
        )  # fmt: skip
    return findings


def check_router(rel: str) -> list[Finding]:
    findings: list[Finding] = []
    tests = "\n".join(backend_tests().values())
    is_webhook = "webhook" in rel
    for route in parse_routes(rel):
        label = f"{route.method} {route.full_path}"
        if not (route.has_response_model or route.has_return_annotation):
            findings.append(
                Finding("tests", "endpoint-no-response-schema", rel,
                        f"{label}: no response_model or return type. Declare a Pydantic response.",
                        route.line, "error", detail=label)
            )  # fmt: skip
        if route.untyped_params and not is_webhook:
            findings.append(
                Finding("tests", "endpoint-untyped-input", rel,
                        f"{label}: parameter(s) {', '.join(route.untyped_params)} are not typed "
                        "with a Pydantic model or validated type.",
                        route.line, "error", detail=f"{label}:{','.join(route.untyped_params)}")
            )  # fmt: skip
        pattern = re.escape(route.path)
        pattern = re.sub(r"\\\{[^}]*\\\}", r"(?:\\{[^}]*\\}|[^/\"'\\s]+)", pattern)
        # Tests call "/api/v1/x" or a helper with "/x": match the path after the version prefix.
        if not re.search(pattern + r"(?![\w-])", tests):
            findings.append(
                Finding("tests", "endpoint-no-tests", rel,
                        f"{label}: no test calls this path. Add a flow test (success, 401/403, "
                        "validation error, not-yours 404).",
                        route.line, "warn", detail=label)
            )  # fmt: skip
    return findings


def check_frontend(rel: str, feature: str, rest: str) -> list[Finding]:
    if re.search(r"\.test\.tsx?$", rel) or rest.endswith(("index", "types")):
        return []
    tests = {t: x for t, x in frontend_tests().items() if f"/features/{feature}/" in t}
    stem = rest.rsplit("/", 1)[-1]
    if not tests:
        return [
            Finding("tests", "feature-no-tests", rel,
                    f"Feature '{feature}' has no test file. Add frontend/src/features/{feature}/"
                    f"{feature}.test.tsx with React Testing Library: render, loading, empty, error "
                    "and success states.",
                    severity="error", detail=feature)
        ]  # fmt: skip
    if rel.endswith(".tsx") and not any(
        re.search(rf"\b{re.escape(stem)}\b", x) for x in tests.values()
    ):
        return [
            Finding("tests", "component-not-tested", rel,
                    f"No test in feature '{feature}' mentions '{stem}'.",
                    severity="warn", detail=stem)
        ]  # fmt: skip
    return []


def run(paths: list[str]) -> Result:
    result = Result("tests")
    for rel in paths:
        service = SERVICE.match(rel)
        router = ROUTER.match(rel)
        feature = FEATURE.match(rel)
        if service and not rel.endswith("__init__.py"):
            module = service["module"] or service["plain"]
            result.findings += check_service(rel, module)
        if router:
            result.findings += check_router(rel)
        if feature:
            result.findings += check_frontend(rel, feature["feature"], feature["rest"])
    if not result.findings:
        result.notes.append("No test gaps found for the files checked.")
    return result
