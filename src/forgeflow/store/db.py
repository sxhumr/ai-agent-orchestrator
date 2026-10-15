"""SQLite persistence for projects, briefs, requirements, open items and agent runs.

Rows keep a few indexed columns for lookups and the full Pydantic model as JSON in
``data``. Requirement versions are append-only: editing inserts a new version row.
The schema is versioned through ``PRAGMA user_version`` and the ``MIGRATIONS`` list.
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from forgeflow.models.execution import RunResult
from forgeflow.models.requirements import (
    AgentRunRecord,
    Brief,
    OpenItem,
    OpenItemStatus,
    Project,
    Requirement,
    utcnow,
)

# Each migration is a tuple of statements applied in one transaction. Never edit a
# released migration; append a new one.
MIGRATIONS: list[tuple[str, ...]] = [
    (
        """CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE briefs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            version INTEGER NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (project_id, version)
        )""",
        """CREATE TABLE agent_runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            data TEXT NOT NULL
        )""",
        """CREATE TABLE requirements (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (project_id, key)
        )""",
        """CREATE TABLE requirement_versions (
            requirement_id TEXT NOT NULL REFERENCES requirements(id),
            version INTEGER NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (requirement_id, version)
        )""",
        """CREATE TABLE open_items (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            key TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (project_id, key)
        )""",
        """CREATE TABLE open_item_requirements (
            open_item_id TEXT NOT NULL REFERENCES open_items(id),
            requirement_id TEXT NOT NULL REFERENCES requirements(id),
            PRIMARY KEY (open_item_id, requirement_id)
        )""",
    ),
]

SCHEMA_VERSION = len(MIGRATIONS)


class StoreError(Exception):
    """A request the store cannot satisfy (missing entity, conflict, bad reference)."""


class NotFoundError(StoreError):
    """The referenced entity does not exist."""


class ConflictError(StoreError):
    """The request clashes with existing state (duplicate, already closed)."""


def default_db_path() -> Path:
    home = os.environ.get("FORGEFLOW_HOME")
    if home:
        return Path(home).expanduser() / "forgeflow.db"
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "forgeflow" / "forgeflow.db"


def migrate(conn: sqlite3.Connection) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise StoreError(
            f"database schema v{current} is newer than this ForgeFlow (v{SCHEMA_VERSION})"
        )
    for version in range(current, SCHEMA_VERSION):
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in MIGRATIONS[version]:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version + 1}")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")


_KEY_SUFFIX = re.compile(r"-(\d+)$")


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Autocommit mode; transactions are explicit via transaction().
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        migrate(self.conn)
        self._tx_depth = 0

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """All-or-nothing block. Nested calls join the outer transaction."""
        if self._tx_depth:
            self._tx_depth += 1
            try:
                yield
            finally:
                self._tx_depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._tx_depth = 1
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")
        finally:
            self._tx_depth = 0

    # Projects

    def create_project(self, project: Project) -> Project:
        try:
            with self.transaction():
                self.conn.execute(
                    "INSERT INTO projects (id, name, data, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        project.id,
                        project.name,
                        project.model_dump_json(),
                        project.created_at.isoformat(),
                        project.updated_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"project {project.name!r} already exists") from exc
        return project

    def get_project(self, name_or_id: str) -> Project:
        row = self.conn.execute(
            "SELECT data FROM projects WHERE name = ? OR id = ?", (name_or_id, name_or_id)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"no project named {name_or_id!r}")
        return Project.model_validate_json(row["data"])

    def list_projects(self) -> list[Project]:
        rows = self.conn.execute("SELECT data FROM projects ORDER BY name").fetchall()
        return [Project.model_validate_json(r["data"]) for r in rows]

    def save_project(self, project: Project) -> Project:
        project = project.model_copy(update={"updated_at": utcnow()})
        with self.transaction():
            cur = self.conn.execute(
                "UPDATE projects SET data = ?, updated_at = ? WHERE id = ?",
                (project.model_dump_json(), project.updated_at.isoformat(), project.id),
            )
            if cur.rowcount != 1:
                raise NotFoundError(f"no project with id {project.id}")
        return project

    # Briefs

    def add_brief(self, project_id: str, content: str, source_name: str | None = None) -> Brief:
        with self.transaction():
            self._require_project(project_id)
            row = self.conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM briefs WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            brief = Brief(
                project_id=project_id,
                version=row["v"] + 1,
                content=content,
                source_name=source_name,
            )
            self.conn.execute(
                "INSERT INTO briefs (id, project_id, version, data, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    brief.id,
                    project_id,
                    brief.version,
                    brief.model_dump_json(),
                    brief.created_at.isoformat(),
                ),
            )
        return brief

    def list_briefs(self, project_id: str) -> list[Brief]:
        rows = self.conn.execute(
            "SELECT data FROM briefs WHERE project_id = ? ORDER BY version", (project_id,)
        ).fetchall()
        return [Brief.model_validate_json(r["data"]) for r in rows]

    def get_brief(self, project_id: str, version: int | None = None) -> Brief:
        if version is None:
            row = self.conn.execute(
                "SELECT data FROM briefs WHERE project_id = ? ORDER BY version DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT data FROM briefs WHERE project_id = ? AND version = ?",
                (project_id, version),
            ).fetchone()
        if row is None:
            which = "brief" if version is None else f"brief v{version}"
            raise NotFoundError(f"project has no {which}")
        return Brief.model_validate_json(row["data"])

    # Agent runs

    def record_agent_run(
        self,
        project_id: str,
        role: str,
        result: RunResult,
        summary: str | None = None,
        task_id: str | None = None,
    ) -> AgentRunRecord:
        record = AgentRunRecord(
            id=str(result.run_id),
            project_id=project_id,
            task_id=task_id,
            role=role,
            runtime=result.runtime,
            session_reference=result.session_id,
            status=result.status.value,
            started_at=result.started_at,
            finished_at=result.finished_at,
            exit_code=result.exit_code,
            cost_usd=result.cost_usd,
            summary=summary,
            error_details=result.error_details,
        )
        with self.transaction():
            self._require_project(project_id)
            self.conn.execute(
                "INSERT INTO agent_runs (id, project_id, role, status, started_at, data)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    project_id,
                    role,
                    record.status,
                    record.started_at.isoformat(),
                    record.model_dump_json(),
                ),
            )
        return record

    def list_agent_runs(self, project_id: str) -> list[AgentRunRecord]:
        rows = self.conn.execute(
            "SELECT data FROM agent_runs WHERE project_id = ? ORDER BY started_at", (project_id,)
        ).fetchall()
        return [AgentRunRecord.model_validate_json(r["data"]) for r in rows]

    # Requirements

    def next_requirement_key(self, project_id: str) -> str:
        return f"REQ-{self._max_key_number('requirements', project_id) + 1:03d}"

    def add_requirement(self, requirement: Requirement) -> Requirement:
        """Insert a brand-new requirement (version 1)."""
        if requirement.version != 1:
            raise StoreError("new requirements must start at version 1")
        try:
            with self.transaction():
                self._require_project(requirement.project_id)
                self.conn.execute(
                    "INSERT INTO requirements (id, project_id, key, created_at)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        requirement.id,
                        requirement.project_id,
                        requirement.key,
                        requirement.created_at.isoformat(),
                    ),
                )
                self._insert_requirement_version(requirement)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"requirement {requirement.key} already exists") from exc
        return requirement

    def update_requirement(
        self, project_id: str, key: str, changes: dict[str, Any], change_note: str | None = None
    ) -> Requirement:
        """Append a new version with ``changes`` applied. Identity fields cannot change."""
        protected = {"id", "project_id", "key", "version", "created_at", "updated_at", "origin"}
        bad = protected & changes.keys()
        if bad:
            raise StoreError(f"cannot change {', '.join(sorted(bad))}")
        with self.transaction():
            current = self.get_requirement(project_id, key)
            data = current.model_dump()
            data.update(changes)
            data.update(
                version=current.version + 1,
                change_note=change_note,
                updated_at=utcnow(),
                generated_by_run_id=changes.get("generated_by_run_id"),
            )
            updated = Requirement.model_validate(data)
            self._insert_requirement_version(updated)
        return updated

    def get_requirement(self, project_id: str, key: str, version: int | None = None) -> Requirement:
        sql = (
            "SELECT v.data FROM requirement_versions v JOIN requirements r"
            " ON r.id = v.requirement_id WHERE r.project_id = ? AND r.key = ?"
        )
        params: tuple[Any, ...] = (project_id, key)
        if version is not None:
            sql += " AND v.version = ?"
            params += (version,)
        row = self.conn.execute(sql + " ORDER BY v.version DESC LIMIT 1", params).fetchone()
        if row is None:
            suffix = "" if version is None else f" v{version}"
            raise NotFoundError(f"no requirement {key}{suffix}")
        return Requirement.model_validate_json(row["data"])

    def list_requirements(self, project_id: str) -> list[Requirement]:
        """Latest version of every requirement, ordered by key."""
        rows = self.conn.execute(
            """SELECT v.data FROM requirement_versions v
               JOIN requirements r ON r.id = v.requirement_id
               WHERE r.project_id = ? AND v.version = (
                   SELECT MAX(version) FROM requirement_versions WHERE requirement_id = r.id)
               ORDER BY r.key""",
            (project_id,),
        ).fetchall()
        return [Requirement.model_validate_json(r["data"]) for r in rows]

    def requirement_history(self, project_id: str, key: str) -> list[Requirement]:
        rows = self.conn.execute(
            """SELECT v.data FROM requirement_versions v
               JOIN requirements r ON r.id = v.requirement_id
               WHERE r.project_id = ? AND r.key = ? ORDER BY v.version""",
            (project_id, key),
        ).fetchall()
        if not rows:
            raise NotFoundError(f"no requirement {key}")
        return [Requirement.model_validate_json(r["data"]) for r in rows]

    def _insert_requirement_version(self, requirement: Requirement) -> None:
        self.conn.execute(
            "INSERT INTO requirement_versions (requirement_id, version, status, data, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                requirement.id,
                requirement.version,
                requirement.status.value,
                requirement.model_dump_json(),
                requirement.updated_at.isoformat(),
            ),
        )

    # Open items

    def next_open_item_key(self, project_id: str) -> str:
        return f"Q-{self._max_key_number('open_items', project_id) + 1:03d}"

    def add_open_item(self, item: OpenItem) -> OpenItem:
        try:
            with self.transaction():
                self._require_project(item.project_id)
                self.conn.execute(
                    "INSERT INTO open_items (id, project_id, key, status, data, created_at,"
                    " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item.id,
                        item.project_id,
                        item.key,
                        item.status.value,
                        self._open_item_json(item),
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                    ),
                )
                self._link_open_item(item)
        except sqlite3.IntegrityError as exc:
            raise StoreError(f"could not add {item.key}: {exc}") from exc
        return item

    def get_open_item(self, project_id: str, key: str) -> OpenItem:
        row = self.conn.execute(
            "SELECT id, data FROM open_items WHERE project_id = ? AND key = ?", (project_id, key)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"no open item {key}")
        return self._load_open_item(row)

    def list_open_items(self, project_id: str, *, include_closed: bool = False) -> list[OpenItem]:
        sql = "SELECT id, data FROM open_items WHERE project_id = ?"
        if not include_closed:
            sql += " AND status = 'open'"
        rows = self.conn.execute(sql + " ORDER BY key", (project_id,)).fetchall()
        return [self._load_open_item(r) for r in rows]

    def resolve_open_item(
        self,
        project_id: str,
        key: str,
        resolution: str,
        resolved_by: str,
        status: OpenItemStatus = OpenItemStatus.RESOLVED,
    ) -> OpenItem:
        if status is OpenItemStatus.OPEN:
            raise StoreError("resolution status must be resolved or dismissed")
        with self.transaction():
            item = self.get_open_item(project_id, key)
            if item.status is not OpenItemStatus.OPEN:
                raise ConflictError(f"{key} is already {item.status.value}")
            now = utcnow()
            item = item.model_copy(
                update={
                    "status": status,
                    "resolution": resolution,
                    "resolved_by": resolved_by,
                    "resolved_at": now,
                    "updated_at": now,
                }
            )
            self.conn.execute(
                "UPDATE open_items SET status = ?, data = ?, updated_at = ? WHERE id = ?",
                (item.status.value, self._open_item_json(item), now.isoformat(), item.id),
            )
        return item

    def _link_open_item(self, item: OpenItem) -> None:
        for req_id in item.related_requirement_ids:
            row = self.conn.execute(
                "SELECT project_id FROM requirements WHERE id = ?", (req_id,)
            ).fetchone()
            if row is None or row["project_id"] != item.project_id:
                raise StoreError(f"{item.key} references unknown requirement {req_id}")
            self.conn.execute(
                "INSERT INTO open_item_requirements (open_item_id, requirement_id) VALUES (?, ?)",
                (item.id, req_id),
            )

    def _load_open_item(self, row: sqlite3.Row) -> OpenItem:
        links = self.conn.execute(
            """SELECT l.requirement_id FROM open_item_requirements l
               JOIN requirements r ON r.id = l.requirement_id
               WHERE l.open_item_id = ? ORDER BY r.key""",
            (row["id"],),
        ).fetchall()
        item = OpenItem.model_validate_json(row["data"])
        return item.model_copy(update={"related_requirement_ids": [r[0] for r in links]})

    @staticmethod
    def _open_item_json(item: OpenItem) -> str:
        # Links live in open_item_requirements so they are reference-checked.
        return item.model_dump_json(exclude={"related_requirement_ids"})

    # Helpers

    def _require_project(self, project_id: str) -> None:
        if self.conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
            return
        raise NotFoundError(f"no project with id {project_id}")

    def _max_key_number(self, table: str, project_id: str) -> int:
        assert table in {"requirements", "open_items"}
        rows = self.conn.execute(
            f"SELECT key FROM {table} WHERE project_id = ?", (project_id,)
        ).fetchall()
        numbers = [int(m.group(1)) for r in rows if (m := _KEY_SUFFIX.search(r["key"]))]
        return max(numbers, default=0)
