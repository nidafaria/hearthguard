"""Unit tests for agent handoffs across graph memory (Step B).

Fields: from_agent, to_agent, project, finding_id, summary, created_at, status (open or picked_up).
Functions: write_handoff, read_open_handoffs(agent, project), mark_picked_up(handoff_id).
"""

import pytest

from core.graph.client import FalkorClient
from core.memory.handoff import mark_picked_up, read_open_handoffs, write_handoff
from core.memory.project import drop_project_graph


@pytest.fixture
def client() -> FalkorClient:
    return FalkorClient()


def test_handoff_lifecycle(client):
    project = "handoff_test_project"
    drop_project_graph(project, client)

    try:
        # 1. Initially zero open handoffs
        open_items = read_open_handoffs("Investigator", project, client)
        assert open_items == []

        # 2. Write handoff from Reader to Investigator
        h = write_handoff(
            from_agent="Reader",
            to_agent="Investigator",
            project=project,
            finding_id="find_001",
            summary="Pressure cluster identified in 2021-Q4",
            client=client,
        )
        assert h["from_agent"] == "Reader"
        assert h["to_agent"] == "Investigator"
        assert h["project"] == project
        assert h["finding_id"] == "find_001"
        assert h["summary"] == "Pressure cluster identified in 2021-Q4"
        assert h["status"] == "open"
        assert isinstance(h["created_at"], int)

        # 3. Read open handoffs for Investigator
        open_items = read_open_handoffs("Investigator", project, client)
        assert len(open_items) == 1
        assert open_items[0]["id"] == h["id"]
        assert open_items[0]["status"] == "open"

        # Read open handoffs for another agent (Skeptic) should return empty
        assert read_open_handoffs("Skeptic", project, client) == []

        # 4. Mark picked up
        picked = mark_picked_up(h["id"], client=client)
        assert picked is not None
        assert picked["id"] == h["id"]
        assert picked["status"] == "picked_up"

        # 5. Investigator now sees zero open handoffs
        open_items_after = read_open_handoffs("Investigator", project, client)
        assert open_items_after == []

    finally:
        drop_project_graph(project, client)
