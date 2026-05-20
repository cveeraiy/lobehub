from app.services.rag_parsing import group_and_rank_files, split_text


def test_split_text_preserves_short_document():
    chunks = split_text("Alpha paragraph.\n\nBeta paragraph.", chunk_size=100)

    assert chunks == ["Alpha paragraph.\n\nBeta paragraph."]


def test_split_text_splits_long_paragraph_with_overlap():
    chunks = split_text("abcdef" * 10, chunk_size=20, overlap=5)

    assert len(chunks) > 1
    assert all(len(chunk) <= 20 for chunk in chunks)


def test_group_and_rank_files_uses_highest_similarity():
    grouped = group_and_rank_files(
        [
            {"id": "c1", "fileId": "f1", "fileName": "A", "similarity": 0.3, "text": "one"},
            {"id": "c2", "fileId": "f1", "fileName": "A", "similarity": 0.8, "text": "two"},
            {"id": "c3", "fileId": "f2", "fileName": "B", "similarity": 0.5, "text": "three"},
        ]
    )

    assert [item["fileId"] for item in grouped] == ["f1", "f2"]
    assert grouped[0]["relevanceScore"] == 0.8
    assert len(grouped[0]["topChunks"]) == 2
