import json

from app.routers.agent_eval import _detect_dataset_format, _parse_dataset_rows


def test_detect_dataset_format_from_filename():
    assert _detect_dataset_format("/tmp/file", "cases.jsonl") == "jsonl"
    assert _detect_dataset_format("/tmp/file", "cases.csv") == "csv"
    assert _detect_dataset_format("/tmp/file", "cases.json") == "json"


def test_parse_csv_dataset_preview():
    parsed = _parse_dataset_rows("input,expected\nhello,world\n", fmt="csv", preview=1)

    assert parsed["headers"] == ["input", "expected"]
    assert parsed["rows"] == [{"input": "hello", "expected": "world"}]
    assert parsed["totalCount"] == 1


def test_parse_json_dataset_from_rows_key():
    parsed = _parse_dataset_rows(json.dumps({"rows": [{"input": "a", "expected": "b"}]}), fmt="json")

    assert parsed["headers"] == ["input", "expected"]
    assert parsed["rows"][0]["input"] == "a"


def test_parse_jsonl_dataset():
    parsed = _parse_dataset_rows('{"input":"a"}\n{"input":"b"}\n', fmt="jsonl")

    assert parsed["totalCount"] == 2
    assert parsed["rows"][1]["input"] == "b"
