"""Real requirements analysis through Claude Code. Opt in with FORGEFLOW_LIVE=1."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from forgeflow.analysis.analyst import analyse_brief
from forgeflow.config import AdapterConfig
from forgeflow.models.requirements import Project
from forgeflow.runtime.claude_code import ClaudeCodeAdapter
from forgeflow.store.db import Store

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("FORGEFLOW_LIVE") != "1", reason="set FORGEFLOW_LIVE=1"),
]

BRIEF = """\
We run a small library. Members must be able to search the catalogue by title or author
and reserve a book that is currently on loan. Staff should get a daily list of
reservations. The system must not store members' home addresses.
"""


def test_brief_becomes_traceable_requirements(tmp_path: Path) -> None:
    with Store(tmp_path / "live.db") as store:
        project = store.create_project(Project(name="library", root_path=tmp_path))
        store.add_brief(project.id, BRIEF)
        outcome = analyse_brief(
            store,
            ClaudeCodeAdapter(AdapterConfig(timeout_s=300)),
            project,
            max_budget_usd=0.75,
            timeout_s=300,
        )
        reqs = store.list_requirements(project.id)

    assert len(reqs) >= 3
    assert all(r.generated_by_run_id == outcome.run.id for r in reqs)
    assert all(r.source is not None and r.source.brief_version == 1 for r in reqs)
    quoted = [r for r in reqs if r.source and r.source.quote_found]
    assert len(quoted) >= len(reqs) // 2, "most requirements should cite the brief verbatim"
    assert any(r.acceptance_criteria for r in reqs)
