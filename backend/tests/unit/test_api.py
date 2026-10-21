from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forgeflow.api.app import create_app
from forgeflow.models.execution import RunStatus
from tests.unit.helpers import BRIEF, FakeAdapter, valid_output


@pytest.fixture
def adapter() -> FakeAdapter:
    return FakeAdapter(valid_output())


@pytest.fixture
def client(tmp_path: Path, adapter: FakeAdapter) -> TestClient:
    app = create_app(
        tmp_path / "api.db",
        adapter_factory=lambda _timeout: adapter,
        allowed_hosts=["testserver"],
    )
    return TestClient(app)


@pytest.fixture
def project(client: TestClient, tmp_path: Path) -> str:
    root = tmp_path / "repo"
    root.mkdir()
    r = client.post("/api/projects", json={"name": "acme", "root_path": str(root)})
    assert r.status_code == 201, r.text
    r = client.post("/api/projects/acme/briefs", json={"content": BRIEF, "source_name": "b.md"})
    assert r.status_code == 201, r.text
    return "acme"


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_project_lifecycle(client: TestClient, project: str) -> None:
    summary = client.get(f"/api/projects/{project}").json()
    assert summary["brief_version"] == 1
    assert summary["requirement_count"] == 0
    assert summary["analysis_running"] is False
    assert [p["project"]["name"] for p in client.get("/api/projects").json()] == ["acme"]

    r = client.post(f"/api/projects/{project}/analysis", json={"max_budget_usd": 0.5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requirement_keys"] == ["REQ-001", "REQ-002", "REQ-003", "REQ-004"]
    assert body["unverified_sources"] == ["REQ-004"]

    summary = client.get(f"/api/projects/{project}").json()
    assert summary["project"]["status"] == "AWAITING_CLARIFICATION"
    assert summary["requirement_count"] == 4
    assert summary["unverified_source_count"] == 1
    assert summary["open_item_count"] == 3
    assert summary["total_cost_usd"] == pytest.approx(0.05)
    assert len(client.get(f"/api/projects/{project}/runs").json()) == 1

    # Running again is refused before any paid call.
    r = client.post(f"/api/projects/{project}/analysis", json={})
    assert r.status_code == 422
    assert "already has requirements" in r.json()["detail"]


def test_edit_requirement_and_history(client: TestClient, project: str) -> None:
    client.post(f"/api/projects/{project}/analysis", json={})
    r = client.patch(
        f"/api/projects/{project}/requirements/REQ-003",
        json={
            "status": "accepted",
            "acceptance_criteria": ["LCP under 2.5s on 4G", " "],
            "change_note": "threshold agreed",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2

    detail = client.get(f"/api/projects/{project}/requirements/REQ-003").json()
    assert [v["version"] for v in detail["history"]] == [1, 2]
    assert detail["requirement"]["acceptance_criteria"] == [
        {"key": "AC-1", "description": "LCP under 2.5s on 4G"}
    ]
    assert [i["key"] for i in detail["open_items"]] == ["Q-001"]

    # No-op and empty edits are rejected instead of creating noise versions.
    r = client.patch(f"/api/projects/{project}/requirements/REQ-003", json={"status": "accepted"})
    assert r.status_code == 400
    assert client.patch(f"/api/projects/{project}/requirements/REQ-003", json={}).status_code == 400
    r = client.patch(f"/api/projects/{project}/requirements/REQ-003", json={"priority": "urgent"})
    assert r.status_code == 422


def test_add_requirement(client: TestClient, project: str) -> None:
    r = client.post(
        f"/api/projects/{project}/requirements",
        json={"title": "Audit log", "description": "Log changes", "acceptance_criteria": ["x"]},
    )
    assert r.status_code == 201
    assert r.json()["key"] == "REQ-001"
    assert r.json()["origin"] == "developer"


def test_resolve_open_item(client: TestClient, project: str) -> None:
    client.post(f"/api/projects/{project}/analysis", json={})
    r = client.post(
        f"/api/projects/{project}/open-items/Q-002/resolve",
        json={"resolution": "Out of scope for v1", "dismiss": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"
    assert r.json()["resolved_by"] == "developer"
    open_keys = [i["key"] for i in client.get(f"/api/projects/{project}/open-items").json()]
    assert open_keys == ["Q-001", "Q-003"]
    all_items = client.get(f"/api/projects/{project}/open-items?include_closed=true").json()
    assert len(all_items) == 3
    r = client.post(
        f"/api/projects/{project}/open-items/Q-002/resolve", json={"resolution": "again"}
    )
    assert r.status_code == 409


def test_errors_map_to_status_codes(client: TestClient, project: str, tmp_path: Path) -> None:
    assert client.get("/api/projects/nope").status_code == 404
    assert client.get(f"/api/projects/{project}/requirements/REQ-999").status_code == 404
    r = client.post("/api/projects", json={"name": "acme", "root_path": str(tmp_path)})
    assert r.status_code == 409
    r = client.post("/api/projects", json={"name": "x", "root_path": str(tmp_path / "missing")})
    assert r.status_code == 400 and "not an existing folder" in r.json()["detail"]
    r = client.post("/api/projects", json={"name": "bad name!", "root_path": str(tmp_path)})
    assert r.status_code == 422
    r = client.post(f"/api/projects/{project}/briefs", json={"content": "   "})
    assert r.status_code == 400


def test_failed_analysis_reports_run(tmp_path: Path) -> None:
    app = create_app(
        tmp_path / "f.db",
        adapter_factory=lambda _t: FakeAdapter(None, RunStatus.FAILED, "exit 1"),
        allowed_hosts=["testserver"],
    )
    client = TestClient(app)
    client.post("/api/projects", json={"name": "p", "root_path": str(tmp_path)})
    client.post("/api/projects/p/briefs", json={"content": BRIEF})
    r = client.post("/api/projects/p/analysis", json={})
    assert r.status_code == 422
    assert r.json()["run_id"]
    assert client.get("/api/projects/p").json()["analysis_running"] is False


def test_concurrent_analysis_is_refused(tmp_path: Path) -> None:
    release = threading.Event()
    started = threading.Event()

    class SlowAdapter(FakeAdapter):
        def run(self, task, **kw):  # type: ignore[no-untyped-def]
            started.set()
            release.wait(5)
            return super().run(task, **kw)

    app = create_app(
        tmp_path / "c.db",
        adapter_factory=lambda _t: SlowAdapter(valid_output()),
        allowed_hosts=["testserver"],
    )
    client = TestClient(app)
    client.post("/api/projects", json={"name": "p", "root_path": str(tmp_path)})
    client.post("/api/projects/p/briefs", json={"content": BRIEF})

    results: list[int] = []
    first = threading.Thread(
        target=lambda: results.append(client.post("/api/projects/p/analysis", json={}).status_code)
    )
    first.start()
    assert started.wait(5)
    assert client.get("/api/projects/p").json()["analysis_running"] is True
    assert client.post("/api/projects/p/analysis", json={}).status_code == 409
    release.set()
    first.join(5)
    assert results == [200]


def test_export_markdown(client: TestClient, project: str) -> None:
    client.post(f"/api/projects/{project}/analysis", json={})
    r = client.get(f"/api/projects/{project}/export.md")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "### REQ-001 — Online repair booking" in r.text


def test_rejects_foreign_host_and_origin(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "h.db"), base_url="http://evil.example")
    assert client.get("/api/health").status_code == 400  # DNS-rebinding guard

    client = TestClient(create_app(tmp_path / "h.db"), base_url="http://127.0.0.1:8765")
    ok = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_serve_refuses_non_loopback(capsys: pytest.CaptureFixture[str]) -> None:
    from forgeflow import cli

    assert cli.main(["serve", "--host", "0.0.0.0"]) == 2
    assert "only listens on" in capsys.readouterr().err
