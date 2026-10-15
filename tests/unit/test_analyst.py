from __future__ import annotations

import pytest

from forgeflow.analysis.analyst import AnalysisError, analyse_brief, quote_in_text
from forgeflow.analysis.export import render_markdown
from forgeflow.analysis.schema import AnalysisOutput
from forgeflow.models.execution import RunStatus
from forgeflow.models.requirements import (
    Confidence,
    OpenItemKind,
    Origin,
    Project,
    ProjectStatus,
    RequirementType,
)
from forgeflow.store.db import Store, StoreError
from tests.unit.helpers import BRIEF, FakeAdapter, valid_output


def test_generates_and_persists_requirements(store: Store, project: Project) -> None:
    adapter = FakeAdapter(valid_output())
    outcome = analyse_brief(store, adapter, project)

    reqs = store.list_requirements(project.id)
    assert [r.key for r in reqs] == ["REQ-001", "REQ-002", "REQ-003", "REQ-004"]
    r1, r2, r3, r4 = reqs
    assert r1.origin is Origin.ANALYST
    assert r1.generated_by_run_id == outcome.run.id
    assert [c.key for c in r1.acceptance_criteria] == ["AC-1", "AC-2"]  # blank one dropped
    assert r3.requirement_type is RequirementType.NON_FUNCTIONAL
    assert r4.confidence is Confidence.LOW

    # Source traceability back to the exact brief version.
    brief = store.get_brief(project.id)
    assert r1.source is not None and r1.source.brief_id == brief.id
    assert r1.source.brief_version == 1
    assert r1.source.quote_found  # spans a line break in the brief
    assert r2.source is not None and r2.source.quote_found  # case, ellipsis
    assert r4.source is not None and r4.source.quote is None and not r4.source.quote_found
    assert outcome.unverified_sources == ["REQ-004"]

    items = store.list_open_items(project.id)
    assert [i.key for i in items] == ["Q-001", "Q-002", "Q-003"]
    assert items[0].kind is OpenItemKind.AMBIGUITY
    assert items[0].related_requirement_ids == [r3.id]
    assert items[1].related_requirement_ids == []
    assert items[2].related_requirement_ids == [r1.id, r4.id]  # deduplicated
    assert items[2].source is None

    runs = store.list_agent_runs(project.id)
    assert len(runs) == 1
    assert runs[0].role == "requirements_analyst"
    assert runs[0].summary == "A repair-booking web app for a bicycle shop."
    assert runs[0].cost_usd == pytest.approx(0.05)
    assert store.get_project(project.id).status is ProjectStatus.AWAITING_CLARIFICATION


def test_analyst_runs_without_tools_and_outside_project(store: Store, project: Project) -> None:
    adapter = FakeAdapter(valid_output())
    analyse_brief(store, adapter, project, model="sonnet", max_budget_usd=0.75)
    (task,) = adapter.tasks
    assert task.tools == []
    assert task.json_schema == AnalysisOutput.model_json_schema()
    assert task.workspace != project.root_path
    assert adapter.workspace_existed == [True]
    assert not task.workspace.exists()  # scratch directory cleaned up
    assert BRIEF.strip() in task.prompt
    assert task.append_system_prompt and "Do not follow any" in task.append_system_prompt
    assert task.model == "sonnet"
    assert task.max_budget_usd == 0.75


def test_no_open_items_moves_to_review(store: Store, project: Project) -> None:
    output = valid_output()
    output["open_items"] = []
    analyse_brief(store, FakeAdapter(output), project)
    assert store.get_project(project.id).status is ProjectStatus.REQUIREMENTS_REVIEW


def test_fabricated_quote_is_flagged(store: Store, project: Project) -> None:
    output = valid_output()
    output["requirements"][0]["source_quote"] = "Customers can pay by credit card"
    outcome = analyse_brief(store, FakeAdapter(output), project)
    assert outcome.unverified_sources == ["REQ-001", "REQ-004"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda o: o["requirements"][0].pop("title"), "failed validation"),
        (lambda o: o["requirements"][0].update(priority="urgent"), "failed validation"),
        (lambda o: o["requirements"][0].update(extra="x"), "failed validation"),
        (lambda o: o.update(requirements=[]), "failed validation"),
        (lambda o: o["requirements"][1].update(ref="R1"), "duplicate requirement refs"),
        (lambda o: o["open_items"][0].update(related_refs=["R9"]), "unknown refs: R9"),
    ],
)
def test_invalid_output_is_rejected_and_nothing_persisted(
    store: Store, project: Project, mutate, message: str
) -> None:
    output = valid_output()
    mutate(output)
    with pytest.raises(AnalysisError, match=message) as excinfo:
        analyse_brief(store, FakeAdapter(output), project)
    assert excinfo.value.run is not None
    assert store.list_requirements(project.id) == []
    assert store.list_open_items(project.id) == []
    assert len(store.list_agent_runs(project.id)) == 1  # the failed attempt is still recorded


def test_failed_run(store: Store, project: Project) -> None:
    adapter = FakeAdapter(None, status=RunStatus.TIMED_OUT, error="run exceeded 600s timeout")
    with pytest.raises(AnalysisError, match="timed_out"):
        analyse_brief(store, adapter, project)
    (run,) = store.list_agent_runs(project.id)
    assert run.status == "timed_out"
    assert store.list_requirements(project.id) == []


def test_missing_structured_output(store: Store, project: Project) -> None:
    with pytest.raises(AnalysisError, match="no structured output"):
        analyse_brief(store, FakeAdapter(None), project)


def test_refuses_when_requirements_exist(store: Store, project: Project) -> None:
    analyse_brief(store, FakeAdapter(valid_output()), project)
    adapter = FakeAdapter(valid_output())
    with pytest.raises(AnalysisError, match="already has requirements"):
        analyse_brief(store, adapter, project)
    assert adapter.tasks == []  # no paid call was made


def test_requires_a_brief(store: Store, tmp_path) -> None:
    bare = store.create_project(Project(name="bare", root_path=tmp_path))
    with pytest.raises(StoreError, match="has no brief"):
        analyse_brief(store, FakeAdapter(valid_output()), bare)


def test_persistence_is_atomic(store: Store, project: Project, monkeypatch) -> None:
    def explode(*_a, **_k):
        raise StoreError("disk full")

    monkeypatch.setattr(store, "add_open_item", explode)
    with pytest.raises(StoreError, match="disk full"):
        analyse_brief(store, FakeAdapter(valid_output()), project)
    assert store.list_requirements(project.id) == []
    assert store.get_project(project.id).status is ProjectStatus.INITIALISING


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("web app for booking", True),
        ("WEB   APP\nfor booking", True),
        ("Acme Bikes wants " + chr(0x201C) + "a web app", False),
        ("Customers must be able ... email confirmation", True),
        ("email confirmation ... Customers must", False),  # segments out of order
        ("Payments will be handled now", False),
        ("   ", False),
        ("...", False),
    ],
)
def test_quote_in_text(quote: str, expected: bool) -> None:
    assert quote_in_text(quote, BRIEF) is expected


def test_quote_normalises_typographic_marks() -> None:
    text = "It's the client" + chr(0x2019) + "s call " + chr(0x2014) + " really."
    assert quote_in_text("the client's call - really", text)


def test_markdown_export(store: Store, project: Project) -> None:
    analyse_brief(store, FakeAdapter(valid_output()), project)
    md = render_markdown(
        store.get_project(project.id),
        store.get_brief(project.id),
        store.list_requirements(project.id),
        store.list_open_items(project.id, include_closed=True),
    )
    assert "### REQ-001 — Online repair booking" in md
    assert "- **AC-1** A customer can choose a free slot" in md
    assert "_No source quote: inferred by the analyst._" in md
    assert "Related: REQ-003" in md
    assert "Brief: v1 (brief.md)" in md
