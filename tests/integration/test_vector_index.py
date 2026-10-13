"""Span indexes (§6.6) on a real FalkorDB.

Hand-worked expectations: the Span written at axis 0 is the nearest to (1, 0.1, 0, ...); the
only Span containing the word "weather" is s1; both index types exist after apply_schema, and a
second apply_schema leaves them unchanged.
"""

from eval import vector_index


def test_indexes_exist_and_answer(client):
    r = vector_index.run(client)
    assert r["fulltext_index"] is True
    assert r["vector_index"] is True
    assert r["nearest_to_axis0"] == ["s0"]
    assert r["fulltext_weather"] == ["s1"]
    assert r["embeddings_from_a_language_model"] is False
