from app.routers.rag_eval import _parse_import_records_content, _score_answer
from app.services.agent_eval.service import _score_expected_output


def test_agent_eval_scores_exact_expected_output():
    score, passed, reasoning = _score_expected_output("The answer is Paris.", "Paris")

    assert score == 1
    assert passed is True
    assert "found" in reasoning


def test_agent_eval_scores_partial_term_overlap():
    score, passed, reasoning = _score_expected_output("retrieval generation", "retrieval augmented generation")

    assert score == 2 / 3
    assert passed is True
    assert "2/3" in reasoning


def test_rag_eval_scores_answer_against_ideal_terms():
    score, passed, reasoning = _score_answer("retrieval augmented generation uses context", "retrieval generation")

    assert score == 1
    assert passed is True
    assert "2/2" in reasoning


def test_rag_eval_import_parser_accepts_jsonl_records():
    records = _parse_import_records_content(
        '{"question":"Q1","ideal":"A1","referenceFiles":"doc.md"}\n'
        '{"question":"Q2","referenceFiles":["a.md","b.md"]}\n'
    )

    assert records == [
        {"question": "Q1", "ideal": "A1", "referenceFiles": "doc.md"},
        {"question": "Q2", "referenceFiles": ["a.md", "b.md"]},
    ]


def test_rag_eval_import_parser_accepts_json_array_records():
    records = _parse_import_records_content('[{"question":"Q1","ideal":"A1"}]')

    assert records == [{"question": "Q1", "ideal": "A1"}]
