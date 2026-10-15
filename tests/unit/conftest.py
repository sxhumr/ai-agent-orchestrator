from __future__ import annotations

from pathlib import Path

import pytest

from forgeflow.models.requirements import Project
from forgeflow.store.db import Store
from tests.unit.helpers import BRIEF


@pytest.fixture
def store(tmp_path: Path):
    s = Store(tmp_path / "ff.db")
    yield s
    s.close()


@pytest.fixture
def project(store: Store, tmp_path: Path) -> Project:
    root = tmp_path / "proj"
    root.mkdir()
    p = store.create_project(Project(name="acme", root_path=root))
    store.add_brief(p.id, BRIEF, "brief.md")
    return p
