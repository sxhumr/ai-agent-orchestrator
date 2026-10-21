"""Projects, briefs, requirements and open items: the persisted requirement model."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class ProjectStatus(StrEnum):
    """Mirrors the workflow states in the spec; transitions are enforced from Milestone 3."""

    INITIALISING = "INITIALISING"
    DISCOVERY = "DISCOVERY"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    REQUIREMENTS_REVIEW = "REQUIREMENTS_REVIEW"


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    root_path: Path
    description: str = ""
    status: ProjectStatus = ProjectStatus.INITIALISING
    configuration: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Brief(BaseModel):
    """One version of the business brief. Versions are immutable."""

    id: str = Field(default_factory=new_id)
    project_id: str
    version: int = Field(ge=1)
    content: str = Field(min_length=1)
    source_name: str | None = Field(default=None, description="File or origin of the text.")
    created_at: datetime = Field(default_factory=utcnow)


class RequirementType(StrEnum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"
    BUSINESS_GOAL = "business_goal"


class Priority(StrEnum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REMOVED = "removed"


class Origin(StrEnum):
    ANALYST = "analyst"
    DEVELOPER = "developer"


class SourceReference(BaseModel):
    """Where in the brief a requirement came from."""

    brief_id: str
    brief_version: int
    quote: str | None = None
    quote_found: bool = Field(
        default=False, description="True when the quote was located verbatim in the brief."
    )


class AcceptanceCriterion(BaseModel):
    key: str = Field(pattern=r"^AC-\d+$")
    description: str = Field(min_length=1)


def numbered_criteria(texts: Iterable[str]) -> list[AcceptanceCriterion]:
    """Number non-blank criteria AC-1, AC-2, ... in order."""
    cleaned = [t.strip() for t in texts if t.strip()]
    return [AcceptanceCriterion(key=f"AC-{i}", description=t) for i, t in enumerate(cleaned, 1)]


class Requirement(BaseModel):
    """One version of a requirement. Editing creates a new version with the same id."""

    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=new_id)
    project_id: str
    key: str = Field(pattern=r"^REQ-\d{3,}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    requirement_type: RequirementType
    priority: Priority = Priority.SHOULD
    source: SourceReference | None = None
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    status: RequirementStatus = RequirementStatus.PROPOSED
    confidence: Confidence = Confidence.MEDIUM
    origin: Origin
    generated_by_run_id: str | None = None
    version: int = Field(default=1, ge=1)
    change_note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def has_unverified_source(self) -> bool:
        """An analyst requirement whose quote wasn't found verbatim in the brief."""
        return self.origin is Origin.ANALYST and not (self.source and self.source.quote_found)


class OpenItemKind(StrEnum):
    ASSUMPTION = "assumption"
    OPEN_QUESTION = "open_question"
    AMBIGUITY = "ambiguity"
    POTENTIAL_CONFLICT = "potential_conflict"


class Impact(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OpenItemStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class OpenItem(BaseModel):
    """An assumption, open question, ambiguity or potential conflict needing a developer."""

    id: str = Field(default_factory=new_id)
    project_id: str
    key: str = Field(pattern=r"^Q-\d{3,}$")
    kind: OpenItemKind
    description: str = Field(min_length=1)
    related_requirement_ids: list[str] = Field(default_factory=list)
    impact: Impact = Impact.MEDIUM
    status: OpenItemStatus = OpenItemStatus.OPEN
    resolution: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    source: SourceReference | None = None
    generated_by_run_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AgentRunRecord(BaseModel):
    """Persisted summary of a runtime invocation (events are not stored)."""

    id: str
    project_id: str
    task_id: str | None = None
    role: str
    runtime: str
    session_reference: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    exit_code: int | None
    cost_usd: float | None
    summary: str | None
    error_details: str | None
