"""Local HTTP API for the GUI. A thin layer over Store and the analyst: no logic of its own.

The API can start paid Claude Code runs and has no authentication, so it only ever
listens on loopback, accepts only localhost Host headers (DNS-rebinding guard) and
only allows the configured GUI origins via CORS.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from forgeflow import __version__
from forgeflow.analysis.analyst import AnalysisError, analyse_brief
from forgeflow.analysis.export import render_markdown
from forgeflow.config import AdapterConfig
from forgeflow.models.requirements import (
    AcceptanceCriterion,
    AgentRunRecord,
    Brief,
    Confidence,
    OpenItem,
    OpenItemStatus,
    Origin,
    Priority,
    Project,
    Requirement,
    RequirementStatus,
    RequirementType,
)
from forgeflow.runtime.claude_code import ClaudeCodeAdapter, RuntimeAdapter
from forgeflow.store.db import ConflictError, NotFoundError, Store, StoreError, default_db_path

DEFAULT_GUI_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "[::1]"]

AdapterFactory = Callable[[float], RuntimeAdapter]


def _default_adapter(timeout_s: float) -> RuntimeAdapter:
    return ClaudeCodeAdapter(AdapterConfig(timeout_s=timeout_s))


# Request and response bodies


class CreateProjectBody(BaseModel):
    name: str
    root_path: str = Field(min_length=1)
    description: str = ""


class AddBriefBody(BaseModel):
    content: str = Field(min_length=1)
    source_name: str | None = None


class GenerateBody(BaseModel):
    model: str | None = None
    max_budget_usd: float = Field(default=1.0, gt=0, le=10)
    timeout_s: float = Field(default=600, gt=0, le=1800)


class CreateRequirementBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    requirement_type: RequirementType = RequirementType.FUNCTIONAL
    priority: Priority = Priority.SHOULD
    acceptance_criteria: list[str] = Field(default_factory=list)


class UpdateRequirementBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    requirement_type: RequirementType | None = None
    priority: Priority | None = None
    status: RequirementStatus | None = None
    confidence: Confidence | None = None
    acceptance_criteria: list[str] | None = None
    change_note: str | None = None


class ResolveBody(BaseModel):
    resolution: str = Field(min_length=1)
    resolved_by: str | None = None
    dismiss: bool = False


class ProjectSummary(BaseModel):
    project: Project
    brief_version: int | None
    requirement_count: int
    requirements_by_status: dict[str, int]
    unverified_source_count: int
    open_item_count: int
    run_count: int
    total_cost_usd: float
    analysis_running: bool


class RequirementDetail(BaseModel):
    requirement: Requirement
    history: list[Requirement]
    open_items: list[OpenItem]


class AnalysisResponse(BaseModel):
    summary: str
    brief_version: int
    run: AgentRunRecord
    requirement_keys: list[str]
    open_item_keys: list[str]
    unverified_sources: list[str]


def _store_dep(request: Request) -> Iterator[Store]:
    # One connection per request; SQLite connections are cheap and not thread-shared.
    store = Store(request.app.state.db_path)
    try:
        yield store
    finally:
        store.close()


StoreDep = Annotated[Store, Depends(_store_dep)]


def _criteria(texts: list[str]) -> list[AcceptanceCriterion]:
    cleaned = [t.strip() for t in texts if t.strip()]
    return [AcceptanceCriterion(key=f"AC-{i}", description=t) for i, t in enumerate(cleaned, 1)]


def _unverified(r: Requirement) -> bool:
    return r.origin is Origin.ANALYST and not (r.source and r.source.quote_found)


def create_app(
    db_path: Path | None = None,
    *,
    adapter_factory: AdapterFactory = _default_adapter,
    allowed_origins: list[str] | None = None,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="ForgeFlow", version=__version__)
    app.state.db_path = db_path or default_db_path()
    running: set[str] = set()
    running_lock = threading.Lock()

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or LOOPBACK_HOSTS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or DEFAULT_GUI_ORIGINS,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(NotFoundError)
    def _not_found(_r: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(ConflictError)
    def _conflict(_r: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(StoreError)
    def _store_error(_r: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(AnalysisError)
    def _analysis_error(_r: Request, exc: AnalysisError) -> JSONResponse:
        body: dict[str, Any] = {"detail": str(exc)}
        if exc.run is not None:
            body["run_id"] = exc.run.id
        return JSONResponse(body, status_code=422)

    @app.exception_handler(ValidationError)
    def _domain_validation(_r: Request, exc: ValidationError) -> JSONResponse:
        messages = [f"{'.'.join(map(str, e['loc'])) or 'value'}: {e['msg']}" for e in exc.errors()]
        return JSONResponse({"detail": "; ".join(messages)}, status_code=422)

    def summarise(store: Store, project: Project) -> ProjectSummary:
        reqs = store.list_requirements(project.id)
        by_status: dict[str, int] = {}
        for r in reqs:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        runs = store.list_agent_runs(project.id)
        briefs = store.list_briefs(project.id)
        return ProjectSummary(
            project=project,
            brief_version=briefs[-1].version if briefs else None,
            requirement_count=len(reqs),
            requirements_by_status=by_status,
            unverified_source_count=sum(_unverified(r) for r in reqs),
            open_item_count=len(store.list_open_items(project.id)),
            run_count=len(runs),
            total_cost_usd=round(sum(r.cost_usd or 0 for r in runs), 4),
            analysis_running=project.id in running,
        )

    # Health

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    # Projects

    @app.get("/api/projects")
    def list_projects(store: StoreDep) -> list[ProjectSummary]:
        return [summarise(store, p) for p in store.list_projects()]

    @app.post("/api/projects", status_code=201)
    def create_project(body: CreateProjectBody, store: StoreDep) -> ProjectSummary:
        root = Path(body.root_path).expanduser().resolve()
        if not root.is_dir():
            raise StoreError(f"{root} is not an existing folder")
        project = store.create_project(
            Project(name=body.name, root_path=root, description=body.description)
        )
        return summarise(store, project)

    @app.get("/api/projects/{name}")
    def get_project(name: str, store: StoreDep) -> ProjectSummary:
        return summarise(store, store.get_project(name))

    @app.get("/api/projects/{name}/runs")
    def list_runs(name: str, store: StoreDep) -> list[AgentRunRecord]:
        return store.list_agent_runs(store.get_project(name).id)

    # Briefs

    @app.get("/api/projects/{name}/briefs")
    def list_briefs(name: str, store: StoreDep) -> list[Brief]:
        return store.list_briefs(store.get_project(name).id)

    @app.post("/api/projects/{name}/briefs", status_code=201)
    def add_brief(name: str, body: AddBriefBody, store: StoreDep) -> Brief:
        if not body.content.strip():
            raise StoreError("the brief is empty")
        project = store.get_project(name)
        return store.add_brief(project.id, body.content, body.source_name)

    # Analysis

    @app.post("/api/projects/{name}/analysis")
    def run_analysis(name: str, body: GenerateBody, store: StoreDep) -> AnalysisResponse:
        project = store.get_project(name)
        with running_lock:
            if project.id in running:
                raise ConflictError("an analysis is already running for this project")
            running.add(project.id)
        try:
            outcome = analyse_brief(
                store,
                adapter_factory(body.timeout_s),
                project,
                model=body.model,
                max_budget_usd=body.max_budget_usd,
                timeout_s=body.timeout_s,
            )
        finally:
            with running_lock:
                running.discard(project.id)
        return AnalysisResponse(
            summary=outcome.summary,
            brief_version=outcome.brief.version,
            run=outcome.run,
            requirement_keys=[r.key for r in outcome.requirements],
            open_item_keys=[i.key for i in outcome.open_items],
            unverified_sources=outcome.unverified_sources,
        )

    # Requirements

    @app.get("/api/projects/{name}/requirements")
    def list_requirements(name: str, store: StoreDep) -> list[Requirement]:
        return store.list_requirements(store.get_project(name).id)

    @app.post("/api/projects/{name}/requirements", status_code=201)
    def create_requirement(name: str, body: CreateRequirementBody, store: StoreDep) -> Requirement:
        project = store.get_project(name)
        with store.transaction():
            return store.add_requirement(
                Requirement(
                    project_id=project.id,
                    key=store.next_requirement_key(project.id),
                    title=body.title,
                    description=body.description,
                    requirement_type=body.requirement_type,
                    priority=body.priority,
                    acceptance_criteria=_criteria(body.acceptance_criteria),
                    confidence=Confidence.HIGH,
                    origin=Origin.DEVELOPER,
                )
            )

    @app.get("/api/projects/{name}/requirements/{key}")
    def get_requirement(name: str, key: str, store: StoreDep) -> RequirementDetail:
        project = store.get_project(name)
        requirement = store.get_requirement(project.id, key)
        items = [
            i
            for i in store.list_open_items(project.id, include_closed=True)
            if requirement.id in i.related_requirement_ids
        ]
        return RequirementDetail(
            requirement=requirement,
            history=store.requirement_history(project.id, key),
            open_items=items,
        )

    @app.patch("/api/projects/{name}/requirements/{key}")
    def update_requirement(
        name: str, key: str, body: UpdateRequirementBody, store: StoreDep
    ) -> Requirement:
        project = store.get_project(name)
        changes = body.model_dump(exclude_unset=True, exclude={"change_note"})
        changes = {k: v for k, v in changes.items() if v is not None}
        if "acceptance_criteria" in changes:
            changes["acceptance_criteria"] = _criteria(changes["acceptance_criteria"])
        if not changes:
            raise StoreError("nothing to change")
        current = store.get_requirement(project.id, key)
        if all(getattr(current, k) == v for k, v in changes.items()):
            raise StoreError("these values match the current version; nothing to save")
        return store.update_requirement(project.id, key, changes, body.change_note)

    # Open items

    @app.get("/api/projects/{name}/open-items")
    def list_open_items(
        name: str, store: StoreDep, include_closed: Annotated[bool, Query()] = False
    ) -> list[OpenItem]:
        return store.list_open_items(store.get_project(name).id, include_closed=include_closed)

    @app.post("/api/projects/{name}/open-items/{key}/resolve")
    def resolve_open_item(name: str, key: str, body: ResolveBody, store: StoreDep) -> OpenItem:
        project = store.get_project(name)
        status = OpenItemStatus.DISMISSED if body.dismiss else OpenItemStatus.RESOLVED
        return store.resolve_open_item(
            project.id, key, body.resolution, body.resolved_by or "developer", status
        )

    # Export

    @app.get("/api/projects/{name}/export.md")
    def export_markdown(name: str, store: StoreDep) -> PlainTextResponse:
        project = store.get_project(name)
        briefs = store.list_briefs(project.id)
        text = render_markdown(
            project,
            briefs[-1] if briefs else None,
            store.list_requirements(project.id),
            store.list_open_items(project.id, include_closed=True),
        )
        return PlainTextResponse(
            text,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{project.name}-requirements.md"'
            },
        )

    return app
