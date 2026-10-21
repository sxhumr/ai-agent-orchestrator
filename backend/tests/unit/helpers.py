"""Shared test data and a fake RuntimeAdapter."""

from __future__ import annotations

import copy
import threading
from datetime import UTC, datetime
from typing import Any

from forgeflow.models.execution import RunResult, RunStatus, TaskSpec
from forgeflow.runtime.claude_code import EventCallback

BRIEF = """\
Acme Bikes wants a web app for booking bicycle repairs.

Customers must be able to book a repair slot online and
receive an email confirmation.
Mechanics should see a daily schedule of bookings.
The site must load quickly on mobile phones.
Payments will be handled later.
"""

# Mocked analyst output. R2's quote uses typographic punctuation and an ellipsis on
# purpose; R4 has no quote (inferred).
VALID_OUTPUT: dict[str, Any] = {
    "summary": "A repair-booking web app for a bicycle shop.",
    "requirements": [
        {
            "ref": "R1",
            "title": "Online repair booking",
            "description": "Customers can book a repair slot online.",
            "requirement_type": "functional",
            "priority": "must",
            "confidence": "high",
            "source_quote": "Customers must be able to book a repair slot online and receive",
            "acceptance_criteria": [
                "A customer can choose a free slot and confirm a booking",
                "  ",
                "A booked slot is no longer offered",
            ],
        },
        {
            "ref": "R2",
            "title": "Mechanic daily schedule",
            "description": "Mechanics see the day's bookings.",
            "requirement_type": "functional",
            "priority": "should",
            "confidence": "high",
            "source_quote": "MECHANICS should see " + chr(0x2026) + " schedule of bookings",
            "acceptance_criteria": ["Schedule lists all bookings for the selected day"],
        },
        {
            "ref": "R3",
            "title": "Fast on mobile",
            "description": "Pages load quickly on mobile phones.",
            "requirement_type": "non_functional",
            "priority": "must",
            "confidence": "medium",
            "source_quote": "The site must load quickly on mobile phones.",
            "acceptance_criteria": [],
        },
        {
            "ref": "R4",
            "title": "Admin can manage slots",
            "description": "Someone must define available slots.",
            "requirement_type": "functional",
            "priority": "should",
            "confidence": "low",
            "source_quote": None,
            "acceptance_criteria": ["An admin can add and remove slots"],
        },
    ],
    "open_items": [
        {
            "kind": "ambiguity",
            "description": "What page-load time counts as quick on mobile?",
            "related_refs": ["R3"],
            "impact": "medium",
            "source_quote": "load quickly",
        },
        {
            "kind": "open_question",
            "description": "When will payments be needed, and are they in scope?",
            "related_refs": [],
            "impact": "high",
            "source_quote": "Payments will be handled later.",
        },
        {
            "kind": "assumption",
            "description": "Assumed slot management is done by shop staff.",
            "related_refs": ["R4", "R1", "R4"],
            "impact": "low",
            "source_quote": None,
        },
    ],
}


def valid_output() -> dict[str, Any]:
    return copy.deepcopy(VALID_OUTPUT)


class FakeAdapter:
    """RuntimeAdapter stand-in returning a canned RunResult."""

    def __init__(
        self,
        structured: Any = None,
        status: RunStatus = RunStatus.SUCCEEDED,
        error: str | None = None,
    ) -> None:
        self.structured = structured
        self.status = status
        self.error = error
        self.tasks: list[TaskSpec] = []
        self.workspace_existed: list[bool] = []

    def run(
        self,
        task: TaskSpec,
        *,
        cancel: threading.Event | None = None,
        on_event: EventCallback | None = None,
    ) -> RunResult:
        self.tasks.append(task)
        self.workspace_existed.append(task.workspace.is_dir())
        now = datetime.now(UTC)
        return RunResult(
            status=self.status,
            exit_code=0 if self.status is RunStatus.SUCCEEDED else 1,
            session_id="fake-session",
            workspace=task.workspace,
            started_at=now,
            finished_at=now,
            duration_s=0.1,
            cost_usd=0.05,
            structured_output=self.structured,
            error_details=self.error,
        )
