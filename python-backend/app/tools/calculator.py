"""Calculator builtin tool — safe math expression evaluation."""

from __future__ import annotations

import ast
import json
import math
import operator
from typing import Any

from app.tools.registry import register

# Allowed operators for safe eval
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Allowed math constants and functions
_NAMES: dict[str, Any] = {
    "pi": math.pi,
    "e": math.e,
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "ceil": math.ceil,
    "floor": math.floor,
}


def _safe_eval(node: ast.expr) -> float | int:
    """Recursively evaluate an AST node with only safe operations."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]

    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))

    if isinstance(node, ast.Call):
        func = _safe_eval(node.func)
        if callable(func):
            args = [_safe_eval(a) for a in node.args]
            return func(*args)

    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def evaluate(expression: str) -> str:
    """Evaluate a math expression safely. Returns the result as a string."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as exc:
        return f"Error: {exc}"


@register(
    "calculator",
    description="Evaluate a mathematical expression. Supports basic arithmetic, "
    "exponents, and math functions (sqrt, sin, cos, log, etc.).",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The mathematical expression to evaluate, e.g. '2 + 3 * 4' or 'sqrt(16)'",
            },
        },
        "required": ["expression"],
    },
)
async def calculator_tool(arguments: dict[str, Any]) -> str:
    expr = arguments.get("expression", "")
    result = evaluate(expr)
    return json.dumps({"expression": expr, "result": result})
