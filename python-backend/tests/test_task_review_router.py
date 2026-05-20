from app.routers.tasks import _build_eval_rubric


def test_build_eval_rubric_maps_frontend_config():
    rubric = _build_eval_rubric(
        {
            "id": "keyword-parity",
            "name": "Keyword parity",
            "type": "keyword",
            "config": {"criteria": ["alpha", "beta"]},
            "threshold": 0.75,
            "weight": 2,
        }
    )

    assert rubric.name == "Keyword parity"
    assert rubric.type == "keyword"
    assert rubric.criteria == "alpha, beta"
    assert rubric.pass_threshold == 0.75
    assert rubric.weight == 2
