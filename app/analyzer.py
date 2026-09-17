import ast
import copy
import io
import json
import keyword
import tokenize
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    line: int | None = None

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "detail": self.detail,
            "line": self.line,
        }


def _syntax_result(code: str) -> tuple[dict, ast.AST | None]:
    try:
        return {"status": "pass", "message": "No syntax errors found."}, ast.parse(code)
    except SyntaxError as error:
        return {
            "status": "error",
            "message": error.msg,
            "line": error.lineno,
            "column": error.offset,
            "text": error.text.strip() if error.text else None,
        }, None


def _nested_loop_depth(node: ast.AST, depth: int = 0) -> int:
    if not isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        return max((_nested_loop_depth(child, depth) for child in ast.iter_child_nodes(node)), default=depth)
    return max(
        depth + 1,
        *(_nested_loop_depth(child, depth + 1) for child in ast.iter_child_nodes(node)),
    )


def _function_metrics(tree: ast.AST) -> tuple[int, int, list[Finding]]:
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    findings: list[Finding] = []
    max_depth = 0
    for function in functions:
        max_depth = max(max_depth, _nested_loop_depth(function))
        end_line = getattr(function, "end_lineno", function.lineno)
        length = end_line - function.lineno + 1
        if length > 40:
            findings.append(Finding("medium", "quality", "Long function", f"{function.name} spans {length} lines; consider extracting smaller units.", function.lineno))
        if len(function.args.args) > 5:
            findings.append(Finding("medium", "quality", "Too many parameters", f"{function.name} accepts {len(function.args.args)} parameters.", function.lineno))
    return len(functions), max_depth, findings


def _complexity(tree: ast.AST) -> dict:
    loops = [node for node in ast.walk(tree) if isinstance(node, (ast.For, ast.AsyncFor, ast.While))]
    max_loop_depth = _nested_loop_depth(tree)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    call_names = {node.func.id for node in calls if isinstance(node.func, ast.Name)}
    if max_loop_depth >= 3:
        estimate = "O(n³+)"
        explanation = "Three or more nested loops detected."
    elif max_loop_depth == 2:
        estimate = "O(n²)"
        explanation = "Nested loops may multiply work as input grows."
    elif {"sort", "sorted"}.intersection(call_names):
        estimate = "O(n log n)"
        explanation = "Sorting operations usually dominate runtime."
    elif loops:
        estimate = "O(n)"
        explanation = "A single loop or linear traversal was detected."
    else:
        estimate = "O(1)"
        explanation = "No input-sized loops or sorting operations were detected."
    return {"estimate": estimate, "explanation": explanation, "loops": len(loops), "max_loop_depth": max_loop_depth}


class _NameNormalizer(ast.NodeTransformer):
    def __init__(self):
        self._names: dict[str, str] = {}

    def _normalize_name(self, name: str) -> str:
        if name not in self._names:
            self._names[name] = f"v{len(self._names)}"
        return self._names[name]

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._normalize_name(node.arg)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = "func"
        node.decorator_list = []
        node.returns = None
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        node.name = "func"
        node.decorator_list = []
        node.returns = None
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if isinstance(node.ctx, (ast.Load, ast.Store)):
            node.id = self._normalize_name(node.id)
        return node


def _duplicate_logic_findings(tree: ast.AST) -> list[Finding]:
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(functions) < 2:
        return []

    normalized: list[tuple[str, str]] = []
    for function in functions:
        cloned = copy.deepcopy(function)
        normalized.append((function.name, ast.unparse(_NameNormalizer().visit(cloned))))

    findings: list[Finding] = []
    for index, (name_a, left) in enumerate(normalized):
        for name_b, right in normalized[index + 1:]:
            similarity = SequenceMatcher(None, left, right).ratio()
            if similarity >= 0.7:
                findings.append(
                    Finding(
                        "medium",
                        "duplicate",
                        "Possible duplicate logic",
                        f"{name_a} and {name_b} share almost identical logic; consider extracting a shared helper.",
                        None,
                    )
                )
    return findings


def _quality_findings(tree: ast.AST, code: str) -> list[Finding]:
    findings: list[Finding] = []
    assigned: dict[str, int] = {}
    used: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                assigned[node.id] = node.lineno
            elif isinstance(node.ctx, ast.Load):
                used[node.id] += 1
    builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
    for name, line in assigned.items():
        if name not in used and not name.startswith("_") and name not in builtins:
            findings.append(Finding("low", "quality", "Possibly unused variable", f"'{name}' is assigned but never read.", line))
        if name in {"foo", "bar", "baz", "temp", "data"}:
            findings.append(Finding("low", "quality", "Vague variable name", f"'{name}' hides intent; prefer a more descriptive name.", line))
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(Finding("medium", "reliability", "Bare exception handler", "Catch a specific exception instead of swallowing every error.", node.lineno))
        if isinstance(node, ast.If) and sum(isinstance(child, ast.If) for child in ast.walk(node)) >= 3:
            findings.append(Finding("medium", "quality", "Deep conditional nesting", "Nested conditions are difficult to scan; consider guard clauses.", node.lineno))
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
        meaningful = [token.string for token in tokens if token.type not in {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER}]
        duplicates = sum(count - 1 for count in Counter(meaningful).values() if count > 3)
        if duplicates > 12:
            findings.append(Finding("low", "quality", "Repeated token patterns", "Several expressions repeat; consider extracting shared logic.", None))
    except (tokenize.TokenError, IndentationError):
        pass
    return findings


def analyze(code: str) -> dict:
    syntax, tree = _syntax_result(code)
    if tree is None:
        return {
            "syntax": syntax,
            "complexity": {
                "estimate": "Unavailable",
                "explanation": "Fix syntax errors before complexity can be estimated.",
                "loops": 0,
                "max_loop_depth": 0,
            },
            "issues": [Finding("critical", "syntax", "Syntax error", syntax["message"], syntax.get("line")).as_dict()],
            "metrics": {"lines": len(code.splitlines()), "functions": 0, "loops": 0, "max_loop_depth": 0},
            "score": 0,
        }
    function_count, max_depth, findings = _function_metrics(tree)
    complexity = _complexity(tree)
    findings.extend(_quality_findings(tree, code))
    findings.extend(_duplicate_logic_findings(tree))
    if complexity["max_loop_depth"] >= 2:
        findings.append(Finding("medium", "complexity", "Nested loops", "Potential quadratic or worse runtime detected.", None))
    if complexity["estimate"] == "O(n log n)":
        findings.append(Finding("info", "complexity", "Sorting cost", "Sorting is efficient for many workloads but still scales with input size.", None))

    suggestions = [
        "Keep functions focused on one responsibility and extract repeated logic into helpers.",
        "Prefer descriptive variable and function names to improve readability.",
        "Review nested loops and high-branching logic for algorithmic bottlenecks.",
    ]
    if any(item.category == "duplicate" for item in findings):
        suggestions.insert(0, "Extract the duplicated logic into a shared helper function to reduce maintenance risk.")
    if complexity["estimate"].startswith("O(n"):
        suggestions.append("Profile the hot path and consider a more efficient data structure for large inputs.")

    summary = (
        "Code is structurally valid and generally readable, but there are a few maintainability or performance concerns worth addressing."
        if findings
        else "The code is clean, consistent, and ready for a quick refactor pass."
    )

    score = max(0, min(100, 100 - sum({"critical": 40, "high": 18, "medium": 10, "low": 4, "info": 1}.get(item.severity, 0) for item in findings)))
    return {
        "syntax": syntax,
        "complexity": complexity,
        "issues": [item.as_dict() for item in findings],
        "summary": summary,
        "recommendations": suggestions,
        "metrics": {"lines": len(code.splitlines()), "functions": function_count, "loops": complexity["loops"], "max_loop_depth": max_depth},
        "score": score,
    }
