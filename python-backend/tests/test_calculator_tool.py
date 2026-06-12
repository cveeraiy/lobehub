import json

import pytest

from app.services.tool_execution.service import execute_tool_call_with_context
from app.tools.calculator import calculator_tool, run_calculator_api


def assert_success(api_name, arguments, content=None):
    result = run_calculator_api(api_name, arguments)

    assert result["success"] is True
    if content is not None:
        assert result["content"] == content
    return result


def assert_error(api_name, arguments, error_type):
    result = run_calculator_api(api_name, arguments)

    assert result["success"] is False
    assert result["error"]["type"] == error_type
    return result


def test_calculate_basic_expression():
    assert_success("calculate", {"expression": "2 + 3 * 4"}, "14")


def test_calculate_unit_conversion():
    result = assert_success("calculate", {"expression": "5 cm to inch"})

    assert result["content"].startswith("1.968503937")
    assert result["content"].endswith(" in")


def test_calculate_degrees_with_precision():
    assert_success("calculate", {"expression": "sin(30 deg)", "precision": 3}, "0.500")


def test_evaluate_with_variables():
    assert_success("evaluate", {"expression": "x^2 + 2*x + 1", "variables": {"x": 5}}, "36")


def test_base_conversion():
    result = assert_success("base", {"fromBase": 16, "number": "FF", "toBase": 10}, "255")

    assert result["state"]["decimalValue"] == 255


def test_sort_numbers():
    result = assert_success("sort", {"numbers": [3, 1, 2]})

    assert result["state"]["sorted"] == ["1", "2", "3"]
    assert result["content"] == '["1", "2", "3"]'


def test_symbolic_calculus_and_limit():
    assert_success("differentiate", {"expression": "x^2", "variable": "x"}, "2*x")
    assert_success("integrate", {"expression": "x^2", "variable": "x"}, "x**3/3")
    assert_success(
        "defintegrate",
        {"expression": "x", "lowerBound": 0, "upperBound": 2, "variable": "x"},
        "2",
    )
    assert_success("limit", {"expression": "sin(x)/x", "point": 0, "variable": "x"}, "1")


def test_solve_single_and_system_equations():
    assert_success("solve", {"equation": ["x^2 - 1 = 0"], "variable": ["x"]}, "['-1', '1']")

    result = assert_success(
        "solve",
        {"equation": ["2*x+y=5", "x-y=1"], "variable": ["x", "y"]},
    )

    assert json.loads(result["content"]) == {"x": "2", "y": "1"}


def test_execute_symbolic_expression():
    assert_success("execute", {"expression": "expand((x+1)^2)"}, "x**2 + 2*x + 1")


def test_errors_keep_ts_style_envelope():
    result = assert_error("base", {"fromBase": 2, "number": "2", "toBase": 10}, "ConversionError")

    assert result["content"] == "Base conversion error: Invalid digit"


@pytest.mark.asyncio
async def test_legacy_calculator_tool_keeps_shape():
    result = json.loads(await calculator_tool({"expression": "sqrt(16)"}))

    assert result == {"expression": "sqrt(16)", "result": "4"}


@pytest.mark.asyncio
async def test_double_underscore_dispatch_with_context():
    result = await execute_tool_call_with_context(
        "lobe-calculator__calculate",
        {"expression": "2^8"},
        session=object(),
        user_id="user-1",
    )

    assert json.loads(result)["content"] == "256"
