"""Command-line interface. Every workflow step is usable from here, GUI or not."""

from __future__ import annotations

import argparse
import getpass
import json
import signal
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import Any

from pydantic import ValidationError

from forgeflow.analysis.analyst import AnalysisError, analyse_brief
from forgeflow.analysis.export import export_requirements
from forgeflow.config import AdapterConfig
from forgeflow.models.execution import RunEvent, TaskSpec
from forgeflow.models.requirements import (
    Confidence,
    OpenItemStatus,
    Origin,
    Priority,
    Project,
    Requirement,
    RequirementStatus,
    RequirementType,
    numbered_criteria,
)
from forgeflow.runtime.claude_code import ClaudeCodeAdapter
from forgeflow.store.db import Store, StoreError, default_db_path

Handler = Callable[[argparse.Namespace], int]


def _values(enum: Any) -> list[str]:
    return [member.value for member in enum]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forgeflow")
    parser.add_argument(
        "--db", type=Path, help="SQLite database (default: $FORGEFLOW_HOME/forgeflow.db)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run = sub.add_parser("run", help="Run one bounded Claude Code task and print the outcome.")
    run.add_argument("--cwd", type=Path, required=True, help="Workspace directory.")
    prompt = run.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt")
    prompt.add_argument("--prompt-file", type=Path)
    run.add_argument(
        "--allowed-tools", default="", help="Comma-separated tools, e.g. 'Read,Edit,Write'."
    )
    run.add_argument("--disallowed-tools", default="")
    run.add_argument("--timeout", type=float, default=600.0, help="Wall-clock limit in seconds.")
    run.add_argument("--max-budget-usd", type=float)
    run.add_argument("--model")
    run.add_argument("--resume", dest="resume_session_id", help="Session id to continue.")
    run.add_argument(
        "--permission-mode",
        default="dontAsk",
        choices=["acceptEdits", "dontAsk", "plan", "manual", "auto"],
    )
    run.add_argument("--events", action="store_true", help="Include raw events in the output.")
    run.add_argument("--quiet", action="store_true", help="Do not stream event types to stderr.")
    run.set_defaults(handler=_cmd_run)

    # serve
    serve = sub.add_parser("serve", help="Start the local API used by the GUI.")
    serve.add_argument("--host", default="127.0.0.1", help="Loopback address only.")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--gui-origin",
        action="append",
        help="Browser origin allowed to call the API (repeatable; default localhost:3000).",
    )
    serve.set_defaults(handler=_cmd_serve)

    # project
    project = sub.add_parser("project", help="Create and inspect projects.").add_subparsers(
        dest="action", required=True
    )
    p = project.add_parser("create")
    p.add_argument("name")
    p.add_argument("--root", type=Path, required=True, help="Existing project directory.")
    p.add_argument("--description", default="")
    p.set_defaults(handler=_cmd_project_create)
    p = project.add_parser("list")
    p.set_defaults(handler=_cmd_project_list)
    p = project.add_parser("show")
    p.add_argument("project")
    p.set_defaults(handler=_cmd_project_show)

    # brief
    brief = sub.add_parser("brief", help="Add or view the business brief.").add_subparsers(
        dest="action", required=True
    )
    p = brief.add_parser("add", help="Add a new brief version.")
    p.add_argument("project")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", type=Path)
    src.add_argument("--text")
    p.set_defaults(handler=_cmd_brief_add)
    p = brief.add_parser("show")
    p.add_argument("project")
    p.add_argument("--version", type=int)
    p.set_defaults(handler=_cmd_brief_show)

    # requirements
    reqs = sub.add_parser("requirements", aliases=["req"], help="Structured requirements.")
    rsub = reqs.add_subparsers(dest="action", required=True)
    p = rsub.add_parser("generate", help="Analyse the latest brief with Claude Code.")
    p.add_argument("project")
    p.add_argument("--model")
    p.add_argument("--max-budget-usd", type=float, default=1.0)
    p.add_argument("--timeout", type=float, default=600.0)
    p.set_defaults(handler=_cmd_req_generate)
    p = rsub.add_parser("list")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=_cmd_req_list)
    p = rsub.add_parser("show")
    p.add_argument("project")
    p.add_argument("key")
    p.add_argument("--version", type=int)
    p.set_defaults(handler=_cmd_req_show)
    p = rsub.add_parser("history")
    p.add_argument("project")
    p.add_argument("key")
    p.set_defaults(handler=_cmd_req_history)
    p = rsub.add_parser("add", help="Add a requirement by hand.")
    p.add_argument("project")
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--type", default="functional", choices=_values(RequirementType))
    p.add_argument("--priority", default="should", choices=_values(Priority))
    p.add_argument("--criterion", action="append", default=[], help="Repeatable.")
    p.set_defaults(handler=_cmd_req_add)
    p = rsub.add_parser("edit", help="Change a requirement (creates a new version).")
    p.add_argument("project")
    p.add_argument("key")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--type", choices=_values(RequirementType))
    p.add_argument("--priority", choices=_values(Priority))
    p.add_argument("--status", choices=_values(RequirementStatus))
    p.add_argument("--confidence", choices=_values(Confidence))
    p.add_argument(
        "--criterion",
        action="append",
        help="Repeatable; replaces all acceptance criteria.",
    )
    p.add_argument("--note", help="Why this changed.")
    p.set_defaults(handler=_cmd_req_edit)
    p = rsub.add_parser("export", help="Write requirements.md and requirements.json.")
    p.add_argument("project")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(handler=_cmd_req_export)

    # questions (open items)
    qs = sub.add_parser("questions", aliases=["q"], help="Open questions and assumptions.")
    qsub = qs.add_subparsers(dest="action", required=True)
    p = qsub.add_parser("list")
    p.add_argument("project")
    p.add_argument("--all", action="store_true", help="Include resolved and dismissed items.")
    p.set_defaults(handler=_cmd_q_list)
    p = qsub.add_parser("resolve")
    p.add_argument("project")
    p.add_argument("key")
    p.add_argument("--answer", required=True)
    p.add_argument("--dismiss", action="store_true", help="Close as not applicable.")
    p.add_argument("--by", default=None, help="Who resolved it (default: current user).")
    p.set_defaults(handler=_cmd_q_resolve)
    return parser


def _store(args: argparse.Namespace) -> Store:
    return Store(args.db or default_db_path())


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


# run


def _cmd_run(args: argparse.Namespace) -> int:
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text()
    task = TaskSpec(
        prompt=prompt,
        workspace=args.cwd,
        allowed_tools=_split(args.allowed_tools),
        disallowed_tools=_split(args.disallowed_tools),
        model=args.model,
        max_budget_usd=args.max_budget_usd,
        resume_session_id=args.resume_session_id,
    )
    adapter = ClaudeCodeAdapter(
        AdapterConfig(timeout_s=args.timeout, permission_mode=args.permission_mode)
    )
    cancel = _install_cancel_handler()

    def _on_event(event: RunEvent) -> None:
        label = event.parse_error or "/".join(p for p in (event.type, event.subtype) if p)
        print(f"[event {event.seq}] {label}", file=sys.stderr)

    result = adapter.run(task, cancel=cancel, on_event=None if args.quiet else _on_event)
    exclude = None if args.events else {"events"}
    print(result.model_dump_json(indent=2, exclude=exclude))
    return 0 if result.succeeded else 1


def _install_cancel_handler() -> threading.Event:
    cancel = threading.Event()

    def _on_signal(_signum: int, _frame: FrameType | None) -> None:
        print("forgeflow: cancelling run...", file=sys.stderr)
        cancel.set()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    return cancel


# serve

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _cmd_serve(args: argparse.Namespace) -> int:
    if args.host not in _LOOPBACK:
        # The API has no authentication and can start paid Claude Code runs.
        print(
            "forgeflow: error: serve only listens on 127.0.0.1, localhost or ::1", file=sys.stderr
        )
        return 2
    import uvicorn

    from forgeflow.api.app import create_app

    db = args.db or default_db_path()
    app = create_app(db, allowed_origins=args.gui_origin)
    print(f"ForgeFlow API on http://{args.host}:{args.port} (database {db})", file=sys.stderr)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


# project


def _cmd_project_create(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise StoreError(f"root is not an existing directory: {root}")
    with _store(args) as store:
        project = store.create_project(
            Project(name=args.name, root_path=root, description=args.description)
        )
    print(f"created project {project.name} ({project.id}) at {root}")
    return 0


def _cmd_project_list(args: argparse.Namespace) -> int:
    with _store(args) as store:
        projects = store.list_projects()
    if not projects:
        print("no projects")
    for p in projects:
        print(f"{p.name:<24} {p.status.value:<24} {p.root_path}")
    return 0


def _cmd_project_show(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        reqs = store.list_requirements(project.id)
        items = store.list_open_items(project.id)
        runs = store.list_agent_runs(project.id)
        try:
            brief_line = f"v{store.get_brief(project.id).version}"
        except StoreError:
            brief_line = "none"
    print(f"{project.name}  [{project.status.value}]")
    print(f"  root:         {project.root_path}")
    if project.description:
        print(f"  description:  {project.description}")
    print(f"  brief:        {brief_line}")
    by_status: dict[str, int] = {}
    for r in reqs:
        by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
    breakdown = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) or "none"
    print(f"  requirements: {len(reqs)} ({breakdown})")
    print(f"  open items:   {len(items)}")
    cost = sum(r.cost_usd or 0 for r in runs)
    print(f"  agent runs:   {len(runs)} (${cost:.4f})")
    return 0


# brief


def _cmd_brief_add(args: argparse.Namespace) -> int:
    if args.file is not None:
        content, source = args.file.read_text(), str(args.file)
    else:
        content, source = args.text, None
    if not content.strip():
        raise StoreError("brief is empty")
    with _store(args) as store:
        project = store.get_project(args.project)
        brief = store.add_brief(project.id, content, source)
    print(f"added brief v{brief.version} to {project.name} ({len(content)} chars)")
    return 0


def _cmd_brief_show(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        brief = store.get_brief(project.id, args.version)
    source = f" from {brief.source_name}" if brief.source_name else ""
    print(f"# brief v{brief.version}{source} ({brief.created_at:%Y-%m-%d %H:%M})\n")
    print(brief.content)
    return 0


# requirements


def _cmd_req_generate(args: argparse.Namespace) -> int:
    adapter = ClaudeCodeAdapter(AdapterConfig(timeout_s=args.timeout))
    with _store(args) as store:
        project = store.get_project(args.project)
        print(f"analysing brief for {project.name} with Claude Code...", file=sys.stderr)
        outcome = analyse_brief(
            store,
            adapter,
            project,
            model=args.model,
            max_budget_usd=args.max_budget_usd,
            timeout_s=args.timeout,
        )
    print(outcome.summary)
    print()
    print(
        f"{len(outcome.requirements)} requirements and {len(outcome.open_items)} open items "
        f"from brief v{outcome.brief.version} (run {outcome.run.id}, "
        f"${outcome.run.cost_usd or 0:.4f})"
    )
    for r in outcome.requirements:
        print(f"  {_req_line(r)}")
    if outcome.unverified_sources:
        print(
            f"\nSource quote missing or not found verbatim: {', '.join(outcome.unverified_sources)}"
        )
    if outcome.open_items:
        print("\nOpen items to resolve (forgeflow questions resolve ...):")
        for item in outcome.open_items:
            print(f"  {item.key} [{item.kind.value}, {item.impact.value}] {item.description}")
    return 0


def _req_line(r: Requirement) -> str:
    flag = "  ?src" if r.has_unverified_source else ""
    return (
        f"{r.key}  {r.status.value:<8} {r.priority.value:<6} {r.requirement_type.value:<14} "
        f"v{r.version}  {r.title}{flag}"
    )


def _cmd_req_list(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        reqs = store.list_requirements(project.id)
    if args.json:
        print(json.dumps([r.model_dump(mode="json") for r in reqs], indent=2))
        return 0
    if not reqs:
        print("no requirements")
    for r in reqs:
        print(_req_line(r))
    return 0


def _cmd_req_show(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        r = store.get_requirement(project.id, args.key, args.version)
        related = [
            i
            for i in store.list_open_items(project.id, include_closed=True)
            if r.id in i.related_requirement_ids
        ]
    print(f"{r.key} v{r.version}: {r.title}")
    print(
        f"  type {r.requirement_type.value} · priority {r.priority.value} · "
        f"status {r.status.value} · confidence {r.confidence.value} · origin {r.origin.value}"
    )
    print(f"\n{r.description}\n")
    if r.source:
        found = "found in brief" if r.source.quote_found else "NOT found verbatim in brief"
        if r.source.quote:
            print(f'Source (brief v{r.source.brief_version}, {found}):\n  "{r.source.quote}"\n')
        else:
            print(f"Source: brief v{r.source.brief_version}, no quote (inferred)\n")
    if r.acceptance_criteria:
        print("Acceptance criteria:")
        for c in r.acceptance_criteria:
            print(f"  {c.key}  {c.description}")
        print()
    if related:
        print("Open items:")
        for i in related:
            print(f"  {i.key} [{i.status.value}] {i.description}")
    if r.change_note:
        print(f"Change note: {r.change_note}")
    return 0


def _cmd_req_history(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        versions = store.requirement_history(project.id, args.key)
    for r in versions:
        who = f"run {r.generated_by_run_id[:8]}" if r.generated_by_run_id else "developer"
        note = f" — {r.change_note}" if r.change_note else ""
        print(f"v{r.version}  {r.updated_at:%Y-%m-%d %H:%M}  {r.status.value:<8} {who}{note}")
        print(f"     {r.title}")
    return 0


def _cmd_req_add(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        with store.transaction():
            r = store.add_requirement(
                Requirement(
                    project_id=project.id,
                    key=store.next_requirement_key(project.id),
                    title=args.title,
                    description=args.description,
                    requirement_type=RequirementType(args.type),
                    priority=Priority(args.priority),
                    acceptance_criteria=numbered_criteria(args.criterion),
                    confidence=Confidence.HIGH,
                    origin=Origin.DEVELOPER,
                )
            )
    print(f"added {r.key}: {r.title}")
    return 0


def _cmd_req_edit(args: argparse.Namespace) -> int:
    changes: dict[str, Any] = {
        name: value
        for name, value in {
            "title": args.title,
            "description": args.description,
            "requirement_type": args.type,
            "priority": args.priority,
            "status": args.status,
            "confidence": args.confidence,
        }.items()
        if value is not None
    }
    if args.criterion is not None:
        changes["acceptance_criteria"] = numbered_criteria(args.criterion)
    if not changes:
        raise StoreError("nothing to change; pass at least one field option")
    with _store(args) as store:
        project = store.get_project(args.project)
        r = store.update_requirement(project.id, args.key, changes, args.note)
    print(f"{r.key} is now v{r.version} ({', '.join(sorted(changes))} changed)")
    return 0


def _cmd_req_export(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        try:
            brief = store.get_brief(project.id)
        except StoreError:
            brief = None
        paths = export_requirements(
            args.out,
            project,
            brief,
            store.list_requirements(project.id),
            store.list_open_items(project.id, include_closed=True),
        )
    for path in paths:
        print(f"wrote {path}")
    return 0


# questions


def _cmd_q_list(args: argparse.Namespace) -> int:
    with _store(args) as store:
        project = store.get_project(args.project)
        items = store.list_open_items(project.id, include_closed=args.all)
        keys = {r.id: r.key for r in store.list_requirements(project.id)}
    if not items:
        print("no open items" if not args.all else "no items")
    for i in items:
        related = ", ".join(keys.get(x, "?") for x in i.related_requirement_ids)
        print(
            f"{i.key}  {i.status.value:<9} {i.kind.value:<18} {i.impact.value:<6} {i.description}"
        )
        if related:
            print(f"       related: {related}")
        if i.resolution:
            print(f"       resolution ({i.resolved_by}): {i.resolution}")
    return 0


def _cmd_q_resolve(args: argparse.Namespace) -> int:
    status = OpenItemStatus.DISMISSED if args.dismiss else OpenItemStatus.RESOLVED
    with _store(args) as store:
        project = store.get_project(args.project)
        item = store.resolve_open_item(
            project.id, args.key, args.answer, args.by or getpass.getuser(), status
        )
        remaining = len(store.list_open_items(project.id))
    print(f"{item.key} {item.status.value}; {remaining} open item(s) remaining")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    handler: Handler = args.handler
    try:
        return handler(args)
    except (StoreError, AnalysisError) as exc:
        print(f"forgeflow: error: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"forgeflow: invalid input: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
