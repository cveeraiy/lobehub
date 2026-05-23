import pytest

from app.services.onboarding.service import (
    MarkdownPatchError,
    apply_markdown_patch,
    format_markdown_patch_error,
)


def assert_patch(source, hunks, expected, applied=1):
    result = apply_markdown_patch(source, hunks)

    assert result["ok"] is True
    assert result["content"] == expected
    assert result["applied"] == applied


def assert_patch_error(source, hunks, code):
    result = apply_markdown_patch(source, hunks)

    assert result["ok"] is False
    assert result["error"]["code"] == code
    assert format_markdown_patch_error(result["error"])


def test_replace_hunk_updates_unique_match():
    assert_patch("Hello world", [{"search": "Hello world", "replace": "Hello there"}], "Hello there")


def test_delete_hunk_removes_matched_region():
    assert_patch("one\ntwo\nthree\n", [{"mode": "delete", "search": "two\n"}], "one\nthree\n")


def test_replace_all_counts_all_matches():
    assert_patch(
        "alpha\nalpha\n",
        [{"search": "alpha", "replace": "beta", "replaceAll": True}],
        "beta\nbeta\n",
        applied=2,
    )


def test_missing_search_is_rejected():
    assert_patch_error("alpha", [{"search": "beta", "replace": "gamma"}], "HUNK_NOT_FOUND")


def test_ambiguous_search_is_rejected_without_replace_all():
    assert_patch_error("x\nx\n", [{"mode": "delete", "search": "x\n"}], "HUNK_AMBIGUOUS")


def test_delete_lines_uses_one_based_inclusive_range():
    assert_patch("a\nb\nc\nd\n", [{"mode": "deleteLines", "startLine": 2, "endLine": 3}], "a\nd\n")


def test_insert_at_appends_with_total_lines_plus_one():
    assert_patch("a\nb\nc", [{"mode": "insertAt", "line": 4, "content": "Z"}], "a\nb\nc\nZ")


def test_replace_lines_swaps_inclusive_range():
    assert_patch(
        "one\ntwo\nthree\nfour\n",
        [{"mode": "replaceLines", "startLine": 2, "endLine": 3, "content": "TWO\nTHREE"}],
        "one\nTWO\nTHREE\nfour\n",
    )


def test_line_hunks_apply_in_descending_anchor_order_after_content_hunks():
    assert_patch(
        "header\nbody\nfoot\n",
        [
            {"mode": "deleteLines", "startLine": 2, "endLine": 2},
            {"search": "header", "replace": "HEADER"},
        ],
        "HEADER\nfoot\n",
        applied=2,
    )


@pytest.mark.parametrize(
    ("hunk", "code"),
    [
        ({"mode": "deleteLines", "startLine": 2, "endLine": 1}, "INVALID_LINE_RANGE"),
        ({"mode": "deleteLines", "startLine": 1, "endLine": 5}, "LINE_OUT_OF_RANGE"),
        ({"mode": "insertAt", "line": 5, "content": "X"}, "LINE_OUT_OF_RANGE"),
    ],
)
def test_invalid_line_hunks_are_rejected(hunk, code):
    assert_patch_error("a\nb\n", [hunk], code)


def test_overlapping_line_hunks_are_rejected():
    assert_patch_error(
        "a\nb\nc\nd\n",
        [
            {"mode": "deleteLines", "startLine": 2, "endLine": 3},
            {"mode": "insertAt", "line": 3, "content": "X"},
        ],
        "LINE_OVERLAP",
    )


def test_markdown_patch_error_exposes_structured_detail():
    result = apply_markdown_patch("alpha", [{"search": "beta", "replace": "gamma"}])

    with pytest.raises(MarkdownPatchError, match="search not found") as exc_info:
        raise MarkdownPatchError(result["error"])

    assert exc_info.value.error["code"] == "HUNK_NOT_FOUND"
