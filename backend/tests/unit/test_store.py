from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from forgeflow.models.requirements import (
    AcceptanceCriterion,
    OpenItem,
    OpenItemKind,
    OpenItemStatus,
    Origin,
    Project,
    Requirement,
    RequirementStatus,
    RequirementType,
)
from forgeflow.store.db import SCHEMA_VERSION, Store, StoreError


def make_req(store: Store, project: Project, title: str = "Thing") -> Requirement:
    return store.add_requirement(
        Requirement(
            project_id=project.id,
            key=store.next_requirement_key(project.id),
            title=title,
            description="desc",
            requirement_type=RequirementType.FUNCTIONAL,
            origin=Origin.DEVELOPER,
        )
    )


def make_item(store: Store, project: Project, related: list[str] | None = None) -> OpenItem:
    return store.add_open_item(
        OpenItem(
            project_id=project.id,
            key=store.next_open_item_key(project.id),
            kind=OpenItemKind.OPEN_QUESTION,
            description="Why?",
            related_requirement_ids=related or [],
        )
    )


def test_migrations_applied_and_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    Store(db).close()
    with Store(db) as store:
        assert store.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    conn = sqlite3.connect(db)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()
    with pytest.raises(StoreError, match="newer"):
        Store(db)


def test_data_survives_reopen(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    with Store(db) as store:
        p = store.create_project(Project(name="p1", root_path=tmp_path))
        make_req(store, p)
    with Store(db) as store:
        assert store.get_project("p1").id == p.id
        assert [r.key for r in store.list_requirements(p.id)] == ["REQ-001"]


def test_project_name_unique_and_lookup(store: Store, tmp_path: Path) -> None:
    p = store.create_project(Project(name="p1", root_path=tmp_path))
    assert store.get_project(p.id).name == "p1"
    with pytest.raises(StoreError, match="already exists"):
        store.create_project(Project(name="p1", root_path=tmp_path))
    with pytest.raises(StoreError, match="no project"):
        store.get_project("nope")


def test_project_name_validated(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Project(name="bad name/../", root_path=tmp_path)


def test_brief_versions_increment(store: Store, project: Project) -> None:
    b2 = store.add_brief(project.id, "second")
    assert b2.version == 2
    assert store.get_brief(project.id).content == "second"
    assert store.get_brief(project.id, 1).source_name == "brief.md"
    with pytest.raises(StoreError):
        store.get_brief(project.id, 9)


def test_requirement_keys_and_versions(store: Store, project: Project) -> None:
    r1 = make_req(store, project, "One")
    r2 = make_req(store, project, "Two")
    assert (r1.key, r2.key) == ("REQ-001", "REQ-002")

    updated = store.update_requirement(
        project.id,
        "REQ-001",
        {
            "title": "One, revised",
            "status": "accepted",
            "acceptance_criteria": [AcceptanceCriterion(key="AC-1", description="works")],
        },
        "clarified",
    )
    assert updated.version == 2
    assert updated.id == r1.id
    assert updated.status is RequirementStatus.ACCEPTED
    assert updated.created_at == r1.created_at

    history = store.requirement_history(project.id, "REQ-001")
    assert [(r.version, r.title) for r in history] == [(1, "One"), (2, "One, revised")]
    assert history[1].change_note == "clarified"
    assert store.get_requirement(project.id, "REQ-001", version=1).title == "One"
    assert [r.title for r in store.list_requirements(project.id)] == ["One, revised", "Two"]


def test_update_rejects_identity_and_invalid_values(store: Store, project: Project) -> None:
    make_req(store, project)
    with pytest.raises(StoreError, match="cannot change"):
        store.update_requirement(project.id, "REQ-001", {"key": "REQ-999"})
    with pytest.raises(ValidationError):
        store.update_requirement(project.id, "REQ-001", {"priority": "urgent"})
    assert len(store.requirement_history(project.id, "REQ-001")) == 1


def test_missing_requirement(store: Store, project: Project) -> None:
    with pytest.raises(StoreError, match="no requirement"):
        store.get_requirement(project.id, "REQ-404")
    with pytest.raises(StoreError, match="no requirement"):
        store.update_requirement(project.id, "REQ-404", {"title": "x"})


def test_open_item_links_are_reference_checked(
    store: Store, project: Project, tmp_path: Path
) -> None:
    r = make_req(store, project)
    item = make_item(store, project, [r.id])
    assert item.key == "Q-001"
    assert store.get_open_item(project.id, "Q-001").related_requirement_ids == [r.id]

    with pytest.raises(StoreError, match="unknown requirement"):
        make_item(store, project, ["does-not-exist"])

    other = store.create_project(Project(name="other", root_path=tmp_path))
    with pytest.raises(StoreError, match="unknown requirement"):
        make_item(store, other, [r.id])
    # The failed inserts left nothing behind.
    assert [i.key for i in store.list_open_items(project.id)] == ["Q-001"]
    assert store.list_open_items(other.id) == []


def test_resolve_open_item(store: Store, project: Project) -> None:
    make_item(store, project)
    make_item(store, project)
    item = store.resolve_open_item(project.id, "Q-001", "Because.", "dev")
    assert item.status is OpenItemStatus.RESOLVED
    assert item.resolved_at is not None
    assert [i.key for i in store.list_open_items(project.id)] == ["Q-002"]
    assert len(store.list_open_items(project.id, include_closed=True)) == 2
    with pytest.raises(StoreError, match="already resolved"):
        store.resolve_open_item(project.id, "Q-001", "again", "dev")
    with pytest.raises(StoreError, match="must be resolved or dismissed"):
        store.resolve_open_item(project.id, "Q-002", "x", "dev", OpenItemStatus.OPEN)
    dismissed = store.resolve_open_item(project.id, "Q-002", "n/a", "dev", OpenItemStatus.DISMISSED)
    assert dismissed.status is OpenItemStatus.DISMISSED


def test_transaction_rolls_back(store: Store, project: Project) -> None:
    with pytest.raises(RuntimeError), store.transaction():
        make_req(store, project)
        with store.transaction():  # nested joins the outer transaction
            make_req(store, project)
        raise RuntimeError("boom")
    assert store.list_requirements(project.id) == []
