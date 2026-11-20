"""Architecture review of the whole codebase (it is fast enough to run on every save).

Rules come from .kiro/steering/architecture.md and backend-guidelines.md:
* no circular imports between backend modules (or between any two backend files)
* vendor SDKs only inside app/integrations; services see provider *interfaces*
* the messaging services (chat, sms) never import a concrete provider
* services call other modules' services, never their repositories
* no upward dependencies (repository -> service, service -> router) and no HTTP types in services
* frontend features do not import other features and do not call fetch directly
Plus hints: duplicated functions and unusually large or complex code.
Hints are a prompt to look, not a verdict. Existing accepted findings live in baselines/architecture.json.
"""

from __future__ import annotations

import ast
import hashlib
import re
from collections import defaultdict

from common import Finding, Result, read_text, walk

VENDOR_SDKS = {
    "twilio", "boto3", "botocore", "aiobotocore", "stripe", "supabase", "openai", "anthropic",
    "sendgrid", "vonage", "nexmo", "messagebird",
}  # fmt: skip
CONCRETE_PROVIDERS = re.compile(
    r"^app\.integrations\.(?:sms\.(?:twilio|mock)|ai\.(?:bedrock|mock)|email\.(?:smtp|mock))$"
)
PROVIDER_PACKAGE = re.compile(r"^app\.integrations\.(?:sms|ai|email)\.")
# Composition roots: the only places allowed to name a concrete provider.
COMPOSITION_ROOTS = {
    "backend/app/api/container.py",
    "backend/app/main.py",
    "backend/app/integrations/sms/factory.py",
    "backend/app/integrations/ai/factory.py",
    "backend/app/integrations/email/factory.py",
}
MESSAGING_FILES = re.compile(
    r"^backend/app/modules/(?:chat|sms)/(?:service|engine|webhooks|gateway|admin_service)\.py$"
)
HTTP_NAMES = {"HTTPException", "Request", "Response", "status", "Depends", "APIRouter", "WebSocket"}
MAX_FUNCTION_LINES = 90
MAX_BRANCHES = 18
MAX_FILE_LINES = 900
MIN_DUPLICATE_STATEMENTS = 6


def module_of(rel: str) -> str:
    """backend/app/modules/sms/service.py -> app.modules.sms.service"""
    dotted = rel.removeprefix("backend/").removesuffix(".py").replace("/", ".")
    return dotted.removesuffix(".__init__")


def package_of(dotted: str) -> str:
    parts = dotted.split(".")
    return ".".join(parts[:3]) if parts[:2] == ["app", "modules"] and len(parts) >= 3 else dotted


class Imports:
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.targets: list[tuple[str, int, list[str]]] = []  # (module, line, names)
        try:
            tree = ast.parse(read_text(rel))
        except SyntaxError:
            self.tree: ast.Module | None = None
            return
        self.tree = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.targets += [(a.name, node.lineno, []) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                self.targets.append((node.module, node.lineno, [a.name for a in node.names]))


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components with more than one node (Tarjan, iterative-safe sizes)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    counter = [0]

    def visit(node: str) -> None:
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in graph.get(node, ()):
            if nxt not in index:
                visit(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return components


def backend_findings() -> list[Finding]:
    findings: list[Finding] = []
    files = [f for f in walk("backend/app", (".py",))]
    known = {module_of(f): f for f in files}
    module_graph: dict[str, set[str]] = defaultdict(set)
    file_graph: dict[str, set[str]] = defaultdict(set)
    functions: dict[str, list[tuple[str, int, int]]] = defaultdict(list)

    for rel in files:
        imports = Imports(rel)
        here = module_of(rel)
        in_modules = rel.startswith("backend/app/modules/")
        in_integrations = rel.startswith("backend/app/integrations/")
        is_router = "router" in rel.rsplit("/", 1)[-1]
        is_service = bool(re.search(r"(service|engine)\.py$", rel))
        is_repository = "repository" in rel.rsplit("/", 1)[-1]

        for target, line, names in imports.targets:
            root = target.split(".")[0]
            if target.startswith("app."):
                # `from app.x import y` may be a module: resolve to the file when it is one.
                resolved = [f"{target}.{n}" for n in names if f"{target}.{n}" in known]
                for dest in resolved or ([target] if target in known else []):
                    file_graph[here].add(dest)
                    if here.startswith("app.modules.") and dest.startswith("app.modules."):
                        if package_of(dest) != package_of(here):
                            module_graph[package_of(here)].add(package_of(dest))

            if root in VENDOR_SDKS and not in_integrations:
                findings.append(
                    Finding("architecture", "vendor-sdk-outside-integrations", rel,
                            f"Imports the vendor SDK '{root}'. Vendor SDKs belong in app/integrations behind an interface.",
                            line, "error", detail=root)
                )  # fmt: skip
            if (
                CONCRETE_PROVIDERS.match(target)
                and rel not in COMPOSITION_ROOTS
                and not in_integrations
            ):
                rule = (
                    "provider-in-messaging-service"
                    if MESSAGING_FILES.match(rel)
                    else "concrete-provider-import"
                )
                findings.append(
                    Finding("architecture", rule, rel,
                            f"Imports the concrete provider '{target}'. Depend on the interface "
                            "(app.integrations.<kind>.base) and inject the provider.",
                            line, "error", detail=target)
                )  # fmt: skip
            if (
                MESSAGING_FILES.match(rel)
                and PROVIDER_PACKAGE.match(target)
                and not re.search(r"\.(base|errors)$", target)
                and not CONCRETE_PROVIDERS.match(target)
            ):
                findings.append(
                    Finding("architecture", "provider-in-messaging-service", rel,
                            f"Messaging code imports '{target}'. Use only the provider interface and errors.",
                            line, "warn", detail=target)
                )  # fmt: skip

            if in_modules and target.startswith("app.modules."):
                other = package_of(target)
                if other != package_of(here) and re.search(
                    r"\.(?:[a-z_]*repository|models)$", target
                ):
                    findings.append(
                        Finding("architecture", "cross-module-internals", rel,
                                f"Imports '{target}' from another module. Call that module's service instead of its repository or models.",
                                line, "warn", detail=target)
                    )  # fmt: skip
            if is_repository and re.search(r"\.[a-z_]*(service|router)$", target):
                findings.append(
                    Finding("architecture", "upward-dependency", rel,
                            f"A repository imports '{target}'. Dependencies point router -> service -> repository.",
                            line, "error", detail=target)
                )  # fmt: skip
            if (
                is_service
                and not is_router
                and root == "fastapi"
                and rel.startswith("backend/app/modules/")
            ):
                bad = sorted(set(names) & HTTP_NAMES)
                if bad:
                    findings.append(
                        Finding("architecture", "http-in-service", rel,
                                f"A service imports HTTP types ({', '.join(bad)}). Raise a domain error from core.exceptions instead.",
                                line, "warn", detail=",".join(bad))
                    )  # fmt: skip
            if (
                is_service
                and re.search(r"\.[a-z_]*router$", target)
                and target.startswith("app.modules.")
            ):
                findings.append(
                    Finding("architecture", "upward-dependency", rel,
                            f"A service imports '{target}'.", line, "error", detail=target)
                )  # fmt: skip

        if imports.tree is None:
            continue
        line_count = len(read_text(rel).splitlines())
        if line_count > MAX_FILE_LINES:
            findings.append(
                Finding("architecture", "large-file", rel,
                        f"{line_count} lines. Consider splitting by responsibility.",
                        severity="info", detail="size")
            )  # fmt: skip
        for node in ast.walk(imports.tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            branches = sum(
                isinstance(
                    n,
                    ast.If
                    | ast.For
                    | ast.While
                    | ast.Try
                    | ast.ExceptHandler
                    | ast.BoolOp
                    | ast.IfExp
                    | ast.comprehension,
                )
                for n in ast.walk(node)
            )
            if length > MAX_FUNCTION_LINES or branches > MAX_BRANCHES:
                findings.append(
                    Finding("architecture", "complex-function", rel,
                            f"'{node.name}' is {length} lines with {branches} branches. Consider extracting single-purpose helpers.",
                            node.lineno, "info", detail=node.name)
                )  # fmt: skip
            statements = sum(isinstance(n, ast.stmt) for n in ast.walk(node)) - 1
            if statements >= MIN_DUPLICATE_STATEMENTS and not node.name.startswith("__"):
                body = [ast.Module(body=node.body, type_ignores=[])]
                normalised = ast.dump(body[0], annotate_fields=False)
                normalised = re.sub(r"Constant\('[^']*'\)", "Constant(S)", normalised)
                digest = hashlib.sha1(normalised.encode(), usedforsecurity=False).hexdigest()  # noqa: S324
                functions[digest].append((rel, node.lineno, statements))

    for component in _cycles(module_graph):
        first = next((f for f in files if package_of(module_of(f)) == component[0]), component[0])
        findings.append(
            Finding("architecture", "circular-module-dependency", first,
                    "Modules depend on each other in a cycle: " + " -> ".join(component)
                    + ". Extract an interface or a domain event.",
                    severity="error", detail="|".join(component))
        )  # fmt: skip
    for component in _cycles(file_graph):
        first = known.get(component[0], component[0])
        findings.append(
            Finding("architecture", "circular-import", first,
                    "Files import each other in a cycle: " + ", ".join(component[:6]),
                    severity="warn", detail="|".join(component))
        )  # fmt: skip

    for digest, places in functions.items():
        unique = sorted({(p[0], p[1]) for p in places})
        if len(unique) > 1:
            for rel, line in unique:
                where = ", ".join(f"{f}:{ln}" for f, ln in unique if (f, ln) != (rel, line))[:200]
                findings.append(
                    Finding("architecture", "duplicate-function-body", rel,
                            f"Same logic also at {where}. Extract it if it is business logic.",
                            line, "info", detail=digest[:12])
                )  # fmt: skip
    return findings


def frontend_findings() -> list[Finding]:
    findings: list[Finding] = []
    feature_import = re.compile(r"""from\s+["']@/features/([^/"']+)""")
    for rel in walk("frontend/src/features", (".ts", ".tsx")):
        if re.search(r"\.test\.tsx?$", rel):
            continue
        own = rel.split("/")[3]
        text = read_text(rel)
        for number, line in enumerate(text.splitlines(), start=1):
            match = feature_import.search(line)
            if match and match.group(1) != own:
                findings.append(
                    Finding("architecture", "feature-imports-feature", rel,
                            f"Feature '{own}' imports feature '{match.group(1)}'. Move shared code to components/shared or lib.",
                            number, "warn", detail=f"{own}->{match.group(1)}")
                )  # fmt: skip
    for rel in walk("frontend/src", (".ts", ".tsx")):
        if rel.startswith("frontend/src/lib/api/") or re.search(r"\.test\.tsx?$|/test/", rel):
            continue
        for number, line in enumerate(read_text(rel).splitlines(), start=1):
            if re.search(r"(?<![\w.])fetch\(", line):
                findings.append(
                    Finding("architecture", "direct-fetch", rel,
                            "Direct fetch(). Go through the typed client in lib/api.",
                            number, "warn", detail=f"fetch:{rel}")
                )  # fmt: skip
    return findings


def run(_paths: list[str]) -> Result:
    result = Result("architecture")
    result.findings = backend_findings() + frontend_findings()
    return result
