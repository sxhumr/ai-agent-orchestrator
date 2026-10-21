"""Seed a demo project for screenshots and trying out the GUI, without a paid Claude run.

The analysis goes through the real ``analyse_brief`` path (schema validation, key
assignment, source-quote checks, agent-run record); only the Claude Code adapter is
replaced by one that returns canned output.

    uv run --project backend python scripts/seed_demo.py --db /tmp/forgeflow-demo/forgeflow.db
"""

from __future__ import annotations

import argparse
import tempfile
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from forgeflow.analysis.analyst import analyse_brief
from forgeflow.models.execution import RunResult, RunStatus, TaskSpec
from forgeflow.models.requirements import OpenItemStatus, Project, RequirementStatus
from forgeflow.runtime.claude_code import EventCallback
from forgeflow.store.db import Store, default_db_path

PROJECT = "repair-shop"

FIRST_BRIEF = """\
Spokes & Sprockets is a two-person bicycle repair shop. Today bookings come in by phone
and WhatsApp, and things get missed.
"""

BRIEF = """\
Spokes & Sprockets is a two-person bicycle repair shop. Today bookings come in by phone
and WhatsApp, and things get missed.

Customers must be able to book a repair slot online and receive an email confirmation.
They should be able to reschedule or cancel up to 24 hours before the slot.

The mechanics need to see a daily schedule of bookings on the workshop tablet, with the
bike details and what the customer reported.

When a repair is finished, the customer should get a message saying the bike is ready
for collection.

The site must load quickly on mobile phones, because most customers book from their
phone. Payments will be handled later; for now customers pay in the shop.
"""

CANNED: dict[str, Any] = {
    "summary": (
        "An online booking system for a small bicycle repair shop, replacing phone and "
        "WhatsApp bookings. It covers customer self-service booking, a workshop schedule "
        "and ready-for-collection notifications. Payments are explicitly out of scope."
    ),
    "requirements": [
        {
            "ref": "R1",
            "title": "Online repair booking",
            "description": "Customers can choose a free repair slot and book it online.",
            "requirement_type": "functional",
            "priority": "must",
            "confidence": "high",
            "source_quote": "Customers must be able to book a repair slot online",
            "acceptance_criteria": [
                "A customer can pick a free slot and confirm a booking",
                "A booked slot is no longer offered to other customers",
            ],
        },
        {
            "ref": "R2",
            "title": "Email confirmation",
            "description": "Each booking sends the customer an email confirmation.",
            "requirement_type": "functional",
            "priority": "must",
            "confidence": "high",
            "source_quote": "receive an email confirmation",
            "acceptance_criteria": [
                "A confirmation email is sent within one minute of booking",
                "The email states the date, time and shop address",
            ],
        },
        {
            "ref": "R3",
            "title": "Reschedule or cancel",
            "description": "Customers can move or cancel a booking until 24 hours before it.",
            "requirement_type": "functional",
            "priority": "should",
            "confidence": "high",
            "source_quote": "reschedule or cancel up to 24 hours before the slot",
            "acceptance_criteria": [
                "Reschedule and cancel are offered until 24 hours before the slot",
                "Within 24 hours the customer is asked to phone the shop instead",
            ],
        },
        {
            "ref": "R4",
            "title": "Workshop daily schedule",
            "description": "Mechanics see the day's bookings, bike details and reported problem.",
            "requirement_type": "functional",
            "priority": "must",
            "confidence": "high",
            "source_quote": "a daily schedule of bookings on the workshop tablet",
            "acceptance_criteria": ["The schedule lists every booking for the selected day"],
        },
        {
            "ref": "R5",
            "title": "Ready-for-collection message",
            "description": "Customers are told when their bike is ready.",
            "requirement_type": "functional",
            "priority": "should",
            "confidence": "medium",
            "source_quote": "the customer should get a message saying the bike is ready",
            "acceptance_criteria": ["Marking a repair finished notifies the customer"],
        },
        {
            "ref": "R6",
            "title": "Fast on mobile",
            "description": "Booking pages load quickly on mobile phones.",
            "requirement_type": "non_functional",
            "priority": "must",
            "confidence": "medium",
            "source_quote": "The site must load quickly on mobile phones",
            "acceptance_criteria": [],
        },
        {
            "ref": "R7",
            "title": "Staff manage opening hours",
            "description": "Shop staff define which slots are bookable.",
            "requirement_type": "functional",
            "priority": "should",
            "confidence": "low",
            # Paraphrased rather than quoted, so the source check flags it.
            "source_quote": "staff set the opening hours",
            "acceptance_criteria": ["Staff can open and close slots for a day"],
        },
    ],
    "open_items": [
        {
            "kind": "open_question",
            "description": "How long is a repair slot, and how many bikes can be booked per slot?",
            "related_refs": ["R1", "R4"],
            "impact": "high",
            "source_quote": "book a repair slot online",
        },
        {
            "kind": "ambiguity",
            "description": "Should the ready-for-collection message be email, SMS or WhatsApp?",
            "related_refs": ["R5"],
            "impact": "medium",
            "source_quote": "the customer should get a message",
        },
        {
            "kind": "ambiguity",
            "description": "What page-load time counts as quick on mobile?",
            "related_refs": ["R6"],
            "impact": "medium",
            "source_quote": "load quickly on mobile phones",
        },
        {
            "kind": "open_question",
            "description": (
                "When will online payments be needed, and should the design allow for them now?"
            ),
            "related_refs": [],
            "impact": "high",
            "source_quote": "Payments will be handled later",
        },
        {
            "kind": "assumption",
            "description": "Assumed one shared staff login on the workshop tablet is enough.",
            "related_refs": ["R4", "R7"],
            "impact": "low",
            "source_quote": None,
        },
    ],
}


class CannedAdapter:
    """RuntimeAdapter stand-in that returns CANNED as the structured output."""

    def run(
        self,
        task: TaskSpec,
        *,
        cancel: threading.Event | None = None,
        on_event: EventCallback | None = None,
    ) -> RunResult:
        finished = datetime.now(UTC)
        return RunResult(
            status=RunStatus.SUCCEEDED,
            exit_code=0,
            session_id="demo-session",
            workspace=task.workspace,
            started_at=finished - timedelta(seconds=41),
            finished_at=finished,
            duration_s=41.0,
            cost_usd=0.14,
            num_turns=1,
            structured_output=CANNED,
        )


def seed(db_path: Path, root: Path) -> None:
    store = Store(db_path)
    try:
        project = store.create_project(
            Project(
                name=PROJECT,
                root_path=root,
                description="Online booking for a two-person bicycle repair shop.",
            )
        )
        store.add_brief(project.id, FIRST_BRIEF, "Phone call notes")
        store.add_brief(project.id, BRIEF, "Kick-off email")
        analyse_brief(store, CannedAdapter(), store.get_project(project.id))

        # A few decisions, so the GUI shows progress, history and a closed question.
        store.update_requirement(
            project.id, "REQ-001", {"status": RequirementStatus.ACCEPTED}, "Accepted"
        )
        store.update_requirement(
            project.id, "REQ-002", {"status": RequirementStatus.ACCEPTED}, "Accepted"
        )
        store.update_requirement(
            project.id,
            "REQ-004",
            {"title": "Workshop schedule on the tablet"},
            "Named the device so the layout is designed for it",
        )
        store.update_requirement(
            project.id, "REQ-004", {"status": RequirementStatus.ACCEPTED}, "Accepted"
        )
        store.resolve_open_item(
            project.id,
            "Q-005",
            "Yes, one shared login. Both mechanics use the same tablet.",
            "developer",
            OpenItemStatus.RESOLVED,
        )
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=None, help="SQLite database to seed.")
    parser.add_argument(
        "--root", type=Path, default=None, help="Project folder (default: a new temp dir)."
    )
    args = parser.parse_args()
    db_path: Path = args.db or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    root: Path = args.root or Path(tempfile.mkdtemp(prefix="repair-shop-"))
    seed(db_path, root)
    print(f"Seeded project {PROJECT!r} into {db_path}")


if __name__ == "__main__":
    main()
