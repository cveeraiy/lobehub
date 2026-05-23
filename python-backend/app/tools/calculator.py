"""Calculator builtin tool — Python parity implementation for lobe-calculator."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import sympy as sp
from pint import UnitRegistry
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
    parse_expr,
)

from app.tools.registry import register, register_context_handler

CALCULATOR_IDENTIFIER = "lobe-calculator"
CALCULATOR_APIS = [
    "base",
    "calculate",
    "defintegrate",
    "differentiate",
    "evaluate",
    "execute",
    "integrate",
    "limit",
    "solve",
    "sort",
]

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_UNIT_REGISTRY = UnitRegistry(autoconvert_offset_to_baseunit=True)
_BASE_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _success(content: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"content": content, "success": True}
    if state is not None:
        result["state"] = state
    return result


def _failure(prefix: str, message: str, error_type: str) -> dict[str, Any]:
    return {
        "content": f"{prefix}: {message}",
        "error": {"message": message, "type": error_type},
        "success": False,
    }


def _safe_symbols(variables: dict[str, Any] | None = None) -> dict[str, Any]:
    names: dict[str, Any] = {
        "E": sp.E,
        "I": sp.I,
        "PI": sp.pi,
        "acos": sp.acos,
        "asin": sp.asin,
        "atan": sp.atan,
        "cos": sp.cos,
        "det": lambda value: sp.Matrix(value).det(),
        "e": sp.E,
        "exp": sp.exp,
        "factor": sp.factor,
        "log": sp.log,
        "ln": sp.log,
        "partfrac": sp.apart,
        "pi": sp.pi,
        "sin": sp.sin,
        "sqrt": sp.sqrt,
        "tan": sp.tan,
    }
    if variables:
        names.update({key: sp.Float(value) for key, value in variables.items()})
    return names


def _normalize_expression(expression: str) -> str:
    normalized = expression.replace("°", " deg ")
    normalized = re.sub(r"\bPI\b", "pi", normalized)
    normalized = re.sub(
        r"(?P<value>(?:\d+(?:\.\d+)?|\.\d+))\s*deg\b",
        r"(\g<value>*pi/180)",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def _parse(expression: str, variables: dict[str, Any] | None = None) -> sp.Expr:
    return parse_expr(
        _normalize_expression(expression),
        evaluate=True,
        global_dict={**sp.__dict__, "__builtins__": {}},
        local_dict=_safe_symbols(variables),
        transformations=_TRANSFORMS,
    )


def _format_value(value: Any, precision: int | None = None) -> str:
    if isinstance(value, (list, tuple)):
        return json.dumps([_format_value(item, precision) for item in value])

    if isinstance(value, sp.MatrixBase):
        return str(value.tolist())

    expr = sp.sympify(value)
    if precision is not None:
        numeric = sp.N(expr, max(precision + 8, 16))
        try:
            return f"{float(numeric):.{precision}f}"
        except (TypeError, ValueError):
            return str(numeric)

    if expr.is_number and not expr.is_Integer:
        return str(sp.N(expr, 12)).rstrip("0").rstrip(".")
    return str(expr)


def _format_decimal(value: float | int, precision: int | None = None) -> str:
    if precision is not None:
        return f"{float(value):.{precision}f}"
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _try_unit_conversion(expression: str, precision: int | None = None) -> str | None:
    if not re.search(r"\s+to\s+", expression, flags=re.IGNORECASE):
        return None
    source, target = re.split(r"\s+to\s+", expression, maxsplit=1, flags=re.IGNORECASE)
    quantity = _UNIT_REGISTRY.parse_expression(source.strip())
    converted = quantity.to(target.strip())
    magnitude = _format_decimal(float(converted.magnitude), precision)
    return f"{magnitude} {converted.units:~}"


def calculate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    precision = arguments.get("precision")
    try:
        converted = _try_unit_conversion(expression, precision)
        result = converted if converted is not None else _format_value(_parse(expression), precision)
        return _success(
            result,
            {"expression": expression, "precision": precision, "result": result},
        )
    except Exception as exc:
        return _failure("Calculation error", str(exc), "CalculationError")


def evaluate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    precision = arguments.get("precision")
    variables = arguments.get("variables") or {}
    try:
        result = _format_value(_parse(expression, variables), precision)
        return _success(
            result,
            {
                "expression": expression,
                "precision": precision,
                "result": result,
                "variables": variables,
            },
        )
    except Exception as exc:
        return _failure("Expression evaluation error", str(exc), "CalculationError")


def sort_numbers(arguments: dict[str, Any]) -> dict[str, Any]:
    numbers = arguments.get("numbers") or []
    mode = arguments.get("mode")
    precision = arguments.get("precision")
    reverse = bool(arguments.get("reverse", False))
    try:
        if len(numbers) < 2:
            return _failure(
                "Comparison error",
                "Insufficient numbers for comparison",
                "ValidationError",
            )
        parsed = [float(number) for number in numbers]
        sorted_numbers = [_format_decimal(number, precision) for number in sorted(parsed, reverse=reverse)]
        largest = _format_decimal(max(parsed), precision)
        smallest = _format_decimal(min(parsed), precision)
        result: str | list[str]
        if mode == "largest":
            result = largest
        elif mode == "smallest":
            result = smallest
        else:
            result = sorted_numbers
        return _success(
            json.dumps(result),
            {
                "largest": largest,
                "mode": mode,
                "originalNumbers": numbers,
                "precision": precision,
                "result": result,
                "reverse": reverse,
                "smallest": smallest,
                "sorted": sorted_numbers,
            },
        )
    except Exception as exc:
        return _failure("Comparison error", str(exc), "ComparisonError")


def base_convert(arguments: dict[str, Any]) -> dict[str, Any]:
    number = str(arguments.get("number", "")).strip().upper().split(".", 1)[0]
    from_base = int(arguments.get("fromBase", 10))
    to_base = int(arguments.get("toBase", 10))
    try:
        if from_base < 2 or from_base > 36 or to_base < 2 or to_base > 36:
            raise ValueError("Base must be between 2 and 36")
        decimal = int(number, from_base)
        if decimal == 0:
            converted = "0"
        else:
            sign = "-" if decimal < 0 else ""
            value = abs(decimal)
            digits: list[str] = []
            while value:
                value, remainder = divmod(value, to_base)
                digits.append(_BASE_DIGITS[remainder])
            converted = sign + "".join(reversed(digits))
        return _success(
            converted,
            {
                "convertedNumber": converted,
                "decimalValue": decimal,
                "originalBase": from_base,
                "originalNumber": arguments.get("number"),
                "targetBase": to_base,
            },
        )
    except Exception as exc:
        message = "Invalid digit" if isinstance(exc, ValueError) else str(exc)
        return _failure("Base conversion error", message, "ConversionError")


def _symbol(name: str | None) -> sp.Symbol:
    return sp.Symbol(name or "x")


def differentiate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    variable = str(arguments.get("variable", "x"))
    try:
        result = _format_value(sp.diff(_parse(expression), _symbol(variable)))
        return _success(result, {"expression": expression, "result": result, "variable": variable})
    except Exception as exc:
        return _failure("Differentiation error", str(exc), "DifferentiationError")


def integrate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    variable = str(arguments.get("variable", "x"))
    try:
        result = _format_value(sp.integrate(_parse(expression), _symbol(variable)))
        return _success(result, {"expression": expression, "result": result, "variable": variable})
    except Exception as exc:
        return _failure("Integration error", str(exc), "IntegrationError")


def defintegrate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    variable = str(arguments.get("variable", "x"))
    lower_bound = arguments.get("lowerBound")
    upper_bound = arguments.get("upperBound")
    try:
        x = _symbol(variable)
        result = _format_value(
            sp.integrate(_parse(expression), (x, _parse(str(lower_bound)), _parse(str(upper_bound))))
        )
        return _success(
            result,
            {
                "expression": expression,
                "lowerBound": lower_bound,
                "result": result,
                "upperBound": upper_bound,
                "variable": variable,
            },
        )
    except Exception as exc:
        return _failure("Definite integration error", str(exc), "DefintegrationError")


def limit(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    variable = str(arguments.get("variable", "x"))
    point = arguments.get("point", "oo")
    try:
        point_expr = sp.oo if str(point).lower() in {"infinity", "inf", "oo"} else _parse(str(point))
        result = _format_value(sp.limit(_parse(expression), _symbol(variable), point_expr))
        return _success(
            result,
            {"expression": expression, "point": point, "result": result, "variable": variable},
        )
    except Exception as exc:
        return _failure("Limit computation error", str(exc), "LimitError")


def solve(arguments: dict[str, Any]) -> dict[str, Any]:
    equations = arguments.get("equation") or []
    variables = arguments.get("variable") or ["x"]
    try:
        symbols = [_symbol(variable) for variable in variables]
        parsed_equations = []
        for equation in equations:
            text = str(equation)
            if "=" in text:
                left, right = text.split("=", 1)
                parsed_equations.append(sp.Eq(_parse(left), _parse(right)))
            else:
                parsed_equations.append(_parse(text))
        target = symbols if len(symbols) > 1 else symbols[0]
        equation_target = parsed_equations[0] if len(parsed_equations) == 1 else parsed_equations
        solution = sp.solve(equation_target, target, dict=len(symbols) > 1)
        if not solution:
            return _failure("Equation solver error", "No solution found", "SolveError")
        if len(symbols) == 1:
            result = str([_format_value(item) for item in solution])
        else:
            first = solution[0] if isinstance(solution, list) else solution
            result = json.dumps({str(key): _format_value(value) for key, value in first.items()}, indent=2)
        return _success(result, {"equation": equations, "result": result, "variable": variables})
    except Exception as exc:
        return _failure("Equation solver error", str(exc), "SolveError")


def execute(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    try:
        result = _format_value(_parse(expression))
        return _success(result, {"expression": expression, "result": result})
    except Exception as exc:
        return _failure("Nerdamer execution error", str(exc), "NerdamerError")


_HANDLERS = {
    "base": base_convert,
    "calculate": calculate,
    "defintegrate": defintegrate,
    "differentiate": differentiate,
    "evaluate": evaluate,
    "execute": execute,
    "integrate": integrate,
    "limit": limit,
    "solve": solve,
    "sort": sort_numbers,
}


def run_calculator_api(api_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = _HANDLERS.get(api_name)
    if not handler:
        return _failure("Calculator error", f"Unknown calculator API: {api_name}", "UnknownApiError")
    return handler(arguments)


async def _calculator_context_dispatch(
    arguments: dict[str, Any],
    session: Any,
    user_id: str,
    *,
    api_name: str = "",
    **kwargs: Any,
) -> str:
    del session, user_id, kwargs
    return _json(run_calculator_api(api_name, arguments))


@register(
    CALCULATOR_IDENTIFIER,
    description="Calculator — mathematical calculations, symbolic algebra, calculus, and base conversion.",
    parameters={
        "type": "object",
        "properties": {
            "api_name": {"type": "string", "enum": CALCULATOR_APIS},
            "arguments": {"type": "object"},
        },
        "required": ["api_name", "arguments"],
    },
)
async def calculator_dispatch_tool(arguments: dict[str, Any]) -> str:
    return _json(run_calculator_api(arguments.get("api_name", ""), arguments.get("arguments") or {}))


@register(
    "calculator",
    description="Evaluate a mathematical expression. Supports arithmetic, units, symbolic math, and functions.",
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
    result = calculate(arguments)
    return _json({"expression": arguments.get("expression", ""), "result": result["content"]})


for _api in CALCULATOR_APIS:
    register_context_handler(f"{CALCULATOR_IDENTIFIER}__{_api}", _calculator_context_dispatch)
