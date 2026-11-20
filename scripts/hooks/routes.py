"""Reads FastAPI route declarations from a router module with `ast`. Nothing is imported or run."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from common import read_text

API_PREFIX = "/api/v1"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
USER_DEPENDENCIES = {"CurrentUserDep", "ActiveUserDep", "AdminUserDep"}


@dataclass
class Route:
    function: str
    method: str
    path: str  # without /api/v1, with the router prefix
    line: int
    has_response_model: bool
    has_return_annotation: bool
    untyped_params: list[str] = field(default_factory=list)
    principal_params: list[str] = field(default_factory=list)
    unused_principals: list[str] = field(default_factory=list)
    path_params: list[str] = field(default_factory=list)
    dependencies_in_decorator: bool = False

    @property
    def full_path(self) -> str:
        return f"{API_PREFIX}{self.path}"


def _annotation_name(node: ast.expr | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Subscript):
        base = _annotation_name(node.value)
        if base == "Annotated" and isinstance(node.slice, ast.Tuple) and node.slice.elts:
            return _annotation_name(node.slice.elts[0])
        return base
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.BinOp):
        return _annotation_name(node.left)
    return ""


def _router_prefixes(tree: ast.Module) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and _annotation_name(node.value.func) == "APIRouter"
        ):
            prefix = ""
            for keyword in node.value.keywords:
                if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                    prefix = str(keyword.value.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    prefixes[target.id] = prefix
    return prefixes


def _uses_name(body: list[ast.stmt], name: str) -> bool:
    return any(
        isinstance(node, ast.Name) and node.id == name for stmt in body for node in ast.walk(stmt)
    )


def parse_routes(rel: str, source: str | None = None) -> list[Route]:
    try:
        tree = ast.parse(source if source is not None else read_text(rel))
    except SyntaxError:
        return []
    prefixes = _router_prefixes(tree)
    routes: list[Route] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id in prefixes
                and decorator.func.attr in HTTP_METHODS
            ):
                continue
            raw = decorator.args[0] if decorator.args else None
            tail = str(raw.value) if isinstance(raw, ast.Constant) else ""
            keywords = {k.arg for k in decorator.keywords}
            path = prefixes[decorator.func.value.id] + tail
            route = Route(
                function=node.name,
                method=decorator.func.attr.upper(),
                path=path,
                line=node.lineno,
                has_response_model="response_model" in keywords,
                has_return_annotation=node.returns is not None,
                path_params=re.findall(r"\{([^}:]+)", path),
                dependencies_in_decorator="dependencies" in keywords,
            )
            args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            for arg in args:
                kind = _annotation_name(arg.annotation)
                if kind in USER_DEPENDENCIES:
                    route.principal_params.append(arg.arg)
                    if kind != "AdminUserDep" and not _uses_name(node.body, arg.arg):
                        route.unused_principals.append(arg.arg)
                elif arg.annotation is None and arg.arg not in {"self", "cls"}:
                    route.untyped_params.append(arg.arg)
                elif (
                    kind in {"dict", "Any", "Mapping", "object"}
                    and arg.arg not in route.path_params
                ):
                    route.untyped_params.append(arg.arg)
            routes.append(route)
    return routes
