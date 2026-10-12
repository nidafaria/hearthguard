"""docs/queries.md is generated from the query constants, and the file must match them.

If this test fails, run `uv run python -m eval.queries_doc` and commit the result.
"""

import importlib

from eval import queries_doc


def test_docs_queries_md_matches_the_code():
    on_disk = queries_doc.OUT.read_text(encoding="utf-8")
    assert on_disk == queries_doc.build(), "docs/queries.md is stale: run eval.queries_doc"


def test_every_registered_query_is_a_real_constant_string():
    for mod, name, _ in queries_doc.REGISTRY:
        value = getattr(importlib.import_module(mod), name)
        assert isinstance(value, str) and value.strip(), f"{mod}.{name} is empty or not a string"


def test_every_query_in_the_doc_is_written_as_a_closed_code_block():
    text = queries_doc.build()
    assert text.count("```cypher") == len(queries_doc.REGISTRY)
    assert text.count("```") == 2 * len(queries_doc.REGISTRY)
