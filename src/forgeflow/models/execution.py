"""Typed models describing a coding-runtime task and its recorded outcome."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskSpec(BaseModel):
    """A bounded unit of work handed to a coding runtime."""

    prompt: str = Field(min_length=1)
    workspace: Path = Field(description="Directory the runtime is confined to.")
    allowed_tools: list[str] = Field(
        default_factory=list,
        description="Tools pre-approved for this run, e.g. ['Read', 'Edit', 'Bash(pytest *)'].",
    )
    disallowed_tools: list[str] = Field(default_factory=list)
    model: str | None = None
    max_budget_usd: float | None = Field(default=None, gt=0)
    append_system_prompt: str | None = None
    resume_session_id: str | None = Field(
        default=None, description="Continue an earlier session instead of starting a new one."
    )
    timeout_s: float | None = Field(default=None, gt=0, description="Overrides the config limit.")


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    LAUNCH_ERROR = "launch_error"
    PROTOCOL_ERROR = "protocol_error"


class RunEvent(BaseModel):
    """One line of the runtime's machine-readable event stream."""

    seq: int
    received_at: datetime
    type: str | None = None
    subtype: str | None = None
    data: dict[str, Any] | None = Field(
        default=None, description="Raw event payload; None when omitted for size."
    )
    payload_omitted: bool = False
    parse_error: str | None = None


class RunResult(BaseModel):
    """The recorded outcome of one runtime invocation."""

    run_id: UUID = Field(default_factory=uuid4)
    runtime: str = "claude_code"
    status: RunStatus
    exit_code: int | None = None
    session_id: str | None = None
    argv: list[str] = Field(
        default_factory=list, description="Launch command; prompt not included."
    )
    workspace: Path
    started_at: datetime
    finished_at: datetime
    duration_s: float
    cost_usd: float | None = None
    num_turns: int | None = None
    is_error: bool | None = None
    result_subtype: str | None = None
    result_text: str | None = None
    result_text_truncated: bool = False
    permission_denials: list[Any] = Field(default_factory=list)
    error_details: str | None = None
    stderr_tail: str = ""
    events: list[RunEvent] = Field(default_factory=list)
    events_dropped: int = Field(default=0, description="Events parsed but not stored (cap hit).")

    @property
    def succeeded(self) -> bool:
        return self.status is RunStatus.SUCCEEDED
