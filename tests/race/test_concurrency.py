"""Orgs, red-team and harden copies on one board all finish while a reader is timed."""

from eval import concurrency


def test_every_task_on_every_graph_finishes():
    r = concurrency.run(orgs=2, workers=3, tasks_per_graph=6)
    assert r["graphs_on_board"] == 6 and r["tasks_done"] == r["tasks"] == 36
    assert r["read_latency_ms"]["samples"] > 0
    assert r["passed"]
