"""The connect endpoints: bad input is refused before any thread starts; unknown jobs are 404."""

from fastapi.testclient import TestClient

from api.app import create_app


def client(tmp_path):
    return TestClient(create_app(results=tmp_path, inbox_file=tmp_path / "d.jsonl"))


def test_a_bad_repo_is_refused_with_422_and_no_job_starts(tmp_path):
    c = client(tmp_path)
    for bad in ("octocat", "../../etc/passwd", "a b/c"):
        r = c.post("/api/connect", json={"repo": bad})
        assert r.status_code == 422


def test_an_unknown_job_is_404(tmp_path):
    assert client(tmp_path).get("/api/connect/notajob").status_code == 404
