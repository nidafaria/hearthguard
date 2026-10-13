"""Span indexes (docs/HEARTHGUARD.md §6.6): the full-text and vector indexes work on a real graph.

Run: uv run python -m eval.vector_index
Builds a throw-away graph, applies the schema, writes three synthetic Spans with hand-made
vectors (unit vectors along axes 0, 1 and 2 of the 384-dimension space), and checks:
  - the FULLTEXT index on Span.text and the VECTOR index on Span.embedding both exist;
  - a full-text query for a word finds exactly the Span that holds it;
  - a nearest-neighbour query for a vector close to axis 0 returns the Span written at axis 0.
The embeddings here are NOT from a language model. The pinned local sentence-transformers model
is not installed (see eval/results/blockers_H.md), so no real Span has been embedded yet.
Writes eval/results/vector_index_run.json.
"""

import json
import uuid
from pathlib import Path

from core.graph.client import FalkorClient
from core.graph.schema import (
    SPAN_VECTOR_DIMENSION,
    SPAN_VECTOR_PROPERTY,
    apply_schema,
    indexes_of_type,
)

RESULT = Path(__file__).resolve().parent / "results" / "vector_index_run.json"
TIMEOUT = 30_000

SPANS = (
    ("s0", "synthetic: please hurry the release along", 0),
    ("s1", "synthetic: the weather is mild today", 1),
    ("s2", "synthetic: thanks for the careful review", 2),
)


def axis(i: int) -> list[float]:
    v = [0.0] * SPAN_VECTOR_DIMENSION
    v[i] = 1.0
    return v


def run(client: FalkorClient) -> dict:
    g = f"scratch_vec_{uuid.uuid4().hex[:8]}"
    try:
        apply_schema(client, g)
        apply_schema(client, g)  # the second run must be a no-op
        for sid, text, i in SPANS:
            client.query(
                g,
                f"CREATE (:Span {{id: $id, text: $text, synthetic: true, "
                f"{SPAN_VECTOR_PROPERTY}: vecf32($v)}})",
                {"id": sid, "text": text, "v": axis(i)},
                timeout_ms=TIMEOUT,
            )
        near = axis(0)
        near[1] = 0.1
        nn = client.query(
            g,
            f"CALL db.idx.vector.queryNodes('Span', '{SPAN_VECTOR_PROPERTY}', 1, vecf32($v)) "
            "YIELD node, score RETURN node.id, score",
            {"v": near},
            timeout_ms=TIMEOUT,
        ).result_set
        ft = client.query(
            g,
            "CALL db.idx.fulltext.queryNodes('Span', 'weather') YIELD node RETURN node.id",
            timeout_ms=TIMEOUT,
        ).result_set
        out = {
            "fulltext_index": ("Span", "text") in indexes_of_type(client, g, "FULLTEXT"),
            "vector_index": ("Span", SPAN_VECTOR_PROPERTY) in indexes_of_type(client, g, "VECTOR"),
            "vector_dimension": SPAN_VECTOR_DIMENSION,
            "nearest_to_axis0": [row[0] for row in nn],
            "fulltext_weather": [row[0] for row in ft],
            "embeddings_from_a_language_model": False,
            "note": "hand-made unit vectors; the pinned sentence-transformers model is not "
            "installed, so no real Span is embedded",
        }
    finally:
        client.drop(g)
    return out


if __name__ == "__main__":
    result = run(FalkorClient())
    RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
