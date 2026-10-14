"""Command-line entry point: ``forgeflow run`` executes one bounded Claude Code task."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path
from types import FrameType

from forgeflow.config import AdapterConfig
from forgeflow.models.execution import RunEvent, TaskSpec
from forgeflow.runtime.claude_code import ClaudeCodeAdapter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forgeflow")
    sub = parser.add_subparsers(dest="command", required=True)

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
    return parser


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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

    cancel = threading.Event()

    def _on_sigint(_signum: int, _frame: FrameType | None) -> None:
        print("forgeflow: cancelling run...", file=sys.stderr)
        cancel.set()

    signal.signal(signal.SIGINT, _on_sigint)
    signal.signal(signal.SIGTERM, _on_sigint)

    def _on_event(event: RunEvent) -> None:
        label = event.parse_error or "/".join(p for p in (event.type, event.subtype) if p)
        print(f"[event {event.seq}] {label}", file=sys.stderr)

    result = adapter.run(task, cancel=cancel, on_event=None if args.quiet else _on_event)
    exclude = None if args.events else {"events"}
    print(result.model_dump_json(indent=2, exclude=exclude))
    return 0 if result.succeeded else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
