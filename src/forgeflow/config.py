"""Runtime configuration for ForgeFlow components."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PermissionMode = Literal["acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"]


class AdapterConfig(BaseModel):
    """Limits and policy for launching Claude Code sessions.

    Every limit is finite so a run can never hang or capture unbounded output.
    """

    claude_command: list[str] = Field(
        default_factory=lambda: ["claude"],
        min_length=1,
        description="Command used to launch the CLI. Tests point this at a fake.",
    )
    timeout_s: float = Field(default=600.0, gt=0, description="Wall-clock limit per run.")
    kill_grace_s: float = Field(
        default=5.0, ge=0, description="Time between SIGTERM and SIGKILL when stopping a run."
    )
    permission_mode: PermissionMode = Field(
        default="dontAsk",
        description="dontAsk denies every tool not explicitly allowed (least privilege).",
    )
    max_events: int = Field(default=1000, gt=0, description="Stored events per run.")
    max_line_bytes: int = Field(
        default=8 * 1024 * 1024, gt=0, description="Longest stdout line that will be parsed."
    )
    max_stored_event_bytes: int = Field(
        default=64 * 1024,
        gt=0,
        description="Events larger than this are stored as a summary without their payload.",
    )
    max_stderr_bytes: int = Field(default=64 * 1024, gt=0, description="Tail of stderr kept.")
    max_result_chars: int = Field(default=20_000, gt=0, description="Final result text kept.")
