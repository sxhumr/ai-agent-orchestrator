"""Adapter that runs one bounded task through Claude Code CLI in headless mode.

Integration surface (verified against Claude Code 2.1.299):

* ``claude -p --output-format stream-json --verbose`` emits one JSON object per
  line. The first is ``{"type": "system", "subtype": "init", "session_id": ...}``
  and the last is ``{"type": "result", "subtype": "success" | ..., "is_error": ...,
  "total_cost_usd": ..., "num_turns": ..., "result": ..., "permission_denials": [...]}``.
* The prompt is read from stdin when no positional prompt is given, which keeps it
  out of argv (no length limit, not visible in ``ps``).
* ``--session-id <uuid>`` presets the session id; ``--resume <id>`` continues one.
* ``--permission-prompts none`` auto-denies anything that would prompt, so a
  headless run can never block waiting for a human.

The CLI has no wall-clock limit of its own; this adapter enforces one and stops
the whole process group on timeout or cancellation.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import IO, Any, Protocol
from uuid import uuid4

from forgeflow.config import AdapterConfig
from forgeflow.models.execution import RunEvent, RunResult, RunStatus, TaskSpec

log = logging.getLogger(__name__)

EventCallback = Callable[[RunEvent], None]

_POLL_INTERVAL_S = 0.05
# How long to wait for output pipes to drain after the process exits.
_DRAIN_TIMEOUT_S = 2.0
_STDERR_CHUNK = 4096


class RuntimeAdapter(Protocol):
    """A coding runtime that executes one bounded task and records the outcome."""

    def run(
        self,
        task: TaskSpec,
        *,
        cancel: threading.Event | None = None,
        on_event: EventCallback | None = None,
    ) -> RunResult: ...


def _now() -> datetime:
    return datetime.now(UTC)


class _StreamState:
    """Everything the stdout reader learns; owned by the reader thread until it joins."""

    def __init__(self, max_events: int) -> None:
        self.max_events = max_events
        self.events: list[RunEvent] = []
        self.events_dropped = 0
        self.session_id: str | None = None
        self.result: dict[str, Any] | None = None

    def record(self, event: RunEvent, data: dict[str, Any] | None) -> None:
        if data is not None:
            if isinstance(data.get("session_id"), str):
                self.session_id = data["session_id"]
            if event.type == "result":
                self.result = data
        if len(self.events) < self.max_events:
            self.events.append(event)
        else:
            self.events_dropped += 1


class ClaudeCodeAdapter:
    """Runs tasks through ``claude -p`` with stream-json output."""

    name = "claude_code"

    def __init__(self, config: AdapterConfig | None = None) -> None:
        self.config = config or AdapterConfig()

    def build_argv(self, task: TaskSpec, session_id: str) -> list[str]:
        cfg = self.config
        argv = [
            *cfg.claude_command,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            cfg.permission_mode,
            "--permission-prompts",
            "none",
        ]
        if task.resume_session_id:
            argv += ["--resume", task.resume_session_id]
        else:
            argv += ["--session-id", session_id]
        if task.allowed_tools:
            argv += ["--allowedTools", ",".join(task.allowed_tools)]
        if task.disallowed_tools:
            argv += ["--disallowedTools", ",".join(task.disallowed_tools)]
        if task.model:
            argv += ["--model", task.model]
        if task.max_budget_usd is not None:
            argv += ["--max-budget-usd", f"{task.max_budget_usd:g}"]
        if task.append_system_prompt:
            argv += ["--append-system-prompt", task.append_system_prompt]
        return argv

    def run(
        self,
        task: TaskSpec,
        *,
        cancel: threading.Event | None = None,
        on_event: EventCallback | None = None,
    ) -> RunResult:
        cfg = self.config
        started_at = _now()
        t0 = time.monotonic()
        workspace = task.workspace.expanduser().resolve()
        session_id = task.resume_session_id or str(uuid4())
        argv = self.build_argv(task, session_id)

        def finish(status: RunStatus, **fields: Any) -> RunResult:
            result = RunResult(
                status=status,
                argv=argv,
                workspace=workspace,
                started_at=started_at,
                finished_at=_now(),
                duration_s=round(time.monotonic() - t0, 3),
                **fields,
            )
            log.info("claude_code run %s finished: %s", result.run_id, result.status)
            return result

        if not workspace.is_dir():
            return finish(
                RunStatus.LAUNCH_ERROR, error_details=f"workspace is not a directory: {workspace}"
            )

        try:
            proc = subprocess.Popen(
                argv,
                cwd=workspace,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,  # own process group, so we can stop all descendants
            )
        except OSError as exc:
            return finish(
                RunStatus.LAUNCH_ERROR, error_details=f"could not launch {argv[0]!r}: {exc}"
            )

        assert proc.stdin and proc.stdout and proc.stderr
        state = _StreamState(cfg.max_events)
        stderr_buf = bytearray()
        threads = [
            threading.Thread(target=_write_stdin, args=(proc.stdin, task.prompt), daemon=True),
            threading.Thread(
                target=self._read_stdout, args=(proc.stdout, state, on_event), daemon=True
            ),
            threading.Thread(
                target=_read_stderr,
                args=(proc.stderr, stderr_buf, cfg.max_stderr_bytes),
                daemon=True,
            ),
        ]
        for t in threads:
            t.start()

        deadline = t0 + (task.timeout_s or cfg.timeout_s)
        stopped: RunStatus | None = None
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                stopped = RunStatus.CANCELLED
                break
            if time.monotonic() >= deadline:
                stopped = RunStatus.TIMED_OUT
                break
            time.sleep(_POLL_INTERVAL_S)

        if stopped is not None:
            self._stop(proc)
        exit_code = proc.wait()

        for t in threads[1:]:
            t.join(_DRAIN_TIMEOUT_S)
        if any(t.is_alive() for t in threads[1:]):
            # A descendant still holds the output pipes open; its group outlived the CLI.
            _signal_group(proc.pid, signal.SIGKILL)
            for t in threads[1:]:
                t.join(_DRAIN_TIMEOUT_S)

        stderr_tail = bytes(stderr_buf).decode("utf-8", errors="replace")
        fields: dict[str, Any] = {
            "exit_code": exit_code,
            "session_id": state.session_id or session_id,
            "stderr_tail": stderr_tail,
            "events": state.events,
            "events_dropped": state.events_dropped,
        }
        fields.update(self._result_fields(state.result))

        if stopped is RunStatus.CANCELLED:
            return finish(stopped, error_details="run cancelled", **fields)
        if stopped is RunStatus.TIMED_OUT:
            limit = task.timeout_s or cfg.timeout_s
            return finish(stopped, error_details=f"run exceeded {limit:g}s timeout", **fields)
        if exit_code != 0:
            detail = f"claude exited with code {exit_code}"
            last_err = stderr_tail.strip().splitlines()[-1:] if stderr_tail.strip() else []
            if last_err:
                detail += f": {last_err[0][:500]}"
            return finish(RunStatus.FAILED, error_details=detail, **fields)
        if state.result is None:
            return finish(
                RunStatus.PROTOCOL_ERROR,
                error_details="claude exited 0 without emitting a result event",
                **fields,
            )
        if fields.get("is_error") or fields.get("result_subtype") != "success":
            return finish(
                RunStatus.FAILED,
                error_details=(
                    f"result reported failure (subtype={fields.get('result_subtype')!r}, "
                    f"is_error={fields.get('is_error')!r})"
                ),
                **fields,
            )
        return finish(RunStatus.SUCCEEDED, **fields)

    def _stop(self, proc: subprocess.Popen[bytes]) -> None:
        _signal_group(proc.pid, signal.SIGTERM)
        try:
            proc.wait(self.config.kill_grace_s)
        except subprocess.TimeoutExpired:
            _signal_group(proc.pid, signal.SIGKILL)
        # Descendants that ignored SIGTERM would keep running after the CLI exits.
        _signal_group(proc.pid, signal.SIGKILL)

    def _read_stdout(
        self, stream: IO[bytes], state: _StreamState, on_event: EventCallback | None
    ) -> None:
        limit = self.config.max_line_bytes
        seq = 0
        while True:
            line = stream.readline(limit + 1)
            if not line:
                break
            if len(line) > limit and not line.endswith(b"\n"):
                _discard_rest_of_line(stream, limit)
                event = RunEvent(
                    seq=seq,
                    received_at=_now(),
                    parse_error=f"line exceeded {limit} bytes; discarded",
                    payload_omitted=True,
                )
                data = None
            else:
                line = line.strip()
                if not line:
                    continue
                event, data = self._parse_line(seq, line)
            seq += 1
            state.record(event, data)
            if on_event is not None:
                try:
                    on_event(event)
                except Exception:
                    log.exception("on_event callback raised; continuing run")

    def _parse_line(self, seq: int, line: bytes) -> tuple[RunEvent, dict[str, Any] | None]:
        received_at = _now()
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return RunEvent(
                seq=seq, received_at=received_at, parse_error=f"invalid JSON: {exc}"
            ), None
        if not isinstance(data, dict):
            return (
                RunEvent(
                    seq=seq, received_at=received_at, parse_error="event is not a JSON object"
                ),
                None,
            )
        etype = data.get("type")
        subtype = data.get("subtype")
        too_big = len(line) > self.config.max_stored_event_bytes
        event = RunEvent(
            seq=seq,
            received_at=received_at,
            type=etype if isinstance(etype, str) else None,
            subtype=subtype if isinstance(subtype, str) else None,
            data=None if too_big else data,
            payload_omitted=too_big,
        )
        return event, data

    def _result_fields(self, result: dict[str, Any] | None) -> dict[str, Any]:
        if result is None:
            return {}
        fields: dict[str, Any] = {}
        if isinstance(result.get("is_error"), bool):
            fields["is_error"] = result["is_error"]
        if isinstance(result.get("subtype"), str):
            fields["result_subtype"] = result["subtype"]
        cost = result.get("total_cost_usd")
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            fields["cost_usd"] = float(cost)
        turns = result.get("num_turns")
        if isinstance(turns, int) and not isinstance(turns, bool):
            fields["num_turns"] = turns
        denials = result.get("permission_denials")
        if isinstance(denials, list):
            fields["permission_denials"] = denials
        text = result.get("result")
        if isinstance(text, str):
            cap = self.config.max_result_chars
            fields["result_text"] = text[:cap]
            fields["result_text_truncated"] = len(text) > cap
        return fields


def _signal_group(pgid: int, sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)


def _write_stdin(stream: IO[bytes], prompt: str) -> None:
    try:
        stream.write(prompt.encode("utf-8"))
        stream.close()
    except OSError:
        pass  # the process exited before reading its input; the exit code tells the story


def _read_stderr(stream: IO[bytes], buf: bytearray, cap: int) -> None:
    while chunk := stream.read1(_STDERR_CHUNK):  # type: ignore[attr-defined]
        buf.extend(chunk)
        if len(buf) > cap:
            del buf[: len(buf) - cap]


def _discard_rest_of_line(stream: IO[bytes], chunk: int) -> None:
    while True:
        rest = stream.readline(chunk)
        if not rest or rest.endswith(b"\n"):
            return
