from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from forgeflow.config import AdapterConfig
from forgeflow.models.execution import RunEvent, RunStatus, TaskSpec
from forgeflow.runtime.claude_code import ClaudeCodeAdapter

FAKE = Path(__file__).with_name("fake_claude.py")


def make_adapter(**overrides: object) -> ClaudeCodeAdapter:
    params: dict[str, object] = {
        "claude_command": [sys.executable, str(FAKE)],
        "timeout_s": 10.0,
        "kill_grace_s": 1.0,
    }
    params.update(overrides)
    return ClaudeCodeAdapter(AdapterConfig.model_validate(params))


@pytest.fixture
def scenario(monkeypatch: pytest.MonkeyPatch):
    def set_scenario(name: str) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_SCENARIO", name)

    return set_scenario


def task(workspace: Path, **kw: object) -> TaskSpec:
    return TaskSpec.model_validate({"prompt": "do the thing", "workspace": workspace, **kw})


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); treat it as dead.
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split()[2] != "Z"
    except FileNotFoundError:
        return False


def test_success_records_outcome(tmp_path: Path, scenario) -> None:
    scenario("success")
    seen: list[RunEvent] = []
    result = make_adapter().run(task(tmp_path), on_event=seen.append)

    assert result.status is RunStatus.SUCCEEDED
    assert result.succeeded
    assert result.exit_code == 0
    assert result.session_id == "fake-session-0001"
    assert result.result_text == "echo:do the thing"
    assert result.cost_usd == pytest.approx(0.0123)
    assert result.num_turns == 2
    assert result.is_error is False
    assert result.error_details is None
    assert [e.type for e in result.events] == ["system", "assistant", "result"]
    assert [e.seq for e in seen] == [0, 1, 2]
    assert result.workspace == tmp_path.resolve()
    assert result.finished_at >= result.started_at


def test_prompt_goes_via_stdin_and_argv_has_safety_flags(
    tmp_path: Path, scenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario("success")
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(record))
    ws = tmp_path / "ws"
    ws.mkdir()

    result = make_adapter().run(
        task(
            ws,
            allowed_tools=["Read", "Edit"],
            disallowed_tools=["Bash"],
            model="sonnet",
            max_budget_usd=0.5,
        )
    )

    seen = json.loads(record.read_text())
    argv = seen["argv"]
    assert seen["stdin"] == "do the thing"
    assert "do the thing" not in argv
    assert seen["cwd"] == str(ws.resolve())
    assert argv[:5] == ["-p", "--output-format", "stream-json", "--verbose", "--permission-mode"]
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--permission-prompts") + 1] == "none"
    assert argv[argv.index("--allowedTools") + 1] == "Read,Edit"
    assert argv[argv.index("--disallowedTools") + 1] == "Bash"
    assert argv[argv.index("--model") + 1] == "sonnet"
    assert argv[argv.index("--max-budget-usd") + 1] == "0.5"
    assert "--session-id" in argv
    assert "--resume" not in argv
    assert "--dangerously-skip-permissions" not in argv
    assert result.argv[2:] == argv


def test_resume_uses_resume_flag(tmp_path: Path) -> None:
    argv = make_adapter().build_argv(task(tmp_path, resume_session_id="abc"), "ignored")
    assert argv[argv.index("--resume") + 1] == "abc"
    assert "--session-id" not in argv


def test_error_result_is_failure(tmp_path: Path, scenario) -> None:
    scenario("error_result")
    result = make_adapter().run(task(tmp_path))
    assert result.status is RunStatus.FAILED
    assert result.exit_code == 0
    assert result.is_error is True
    assert result.result_subtype == "error_max_budget_usd"
    assert "error_max_budget_usd" in (result.error_details or "")


def test_nonzero_exit_is_failure_with_stderr(tmp_path: Path, scenario) -> None:
    scenario("nonzero")
    result = make_adapter().run(task(tmp_path))
    assert result.status is RunStatus.FAILED
    assert result.exit_code == 3
    assert "fatal: boom" in (result.error_details or "")
    assert "something went wrong" in result.stderr_tail


def test_missing_result_event_is_protocol_error(tmp_path: Path, scenario) -> None:
    scenario("no_result")
    result = make_adapter().run(task(tmp_path))
    assert result.status is RunStatus.PROTOCOL_ERROR
    assert result.exit_code == 0
    assert result.session_id == "fake-session-0001"


def test_malformed_lines_are_recorded_not_fatal(tmp_path: Path, scenario) -> None:
    scenario("malformed")
    result = make_adapter().run(task(tmp_path))
    assert result.status is RunStatus.SUCCEEDED
    errors = [e.parse_error for e in result.events if e.parse_error]
    assert len(errors) == 2
    assert errors[0].startswith("invalid JSON")
    assert errors[1] == "event is not a JSON object"


def test_timeout_stops_run(tmp_path: Path, scenario) -> None:
    scenario("hang")
    start = time.monotonic()
    result = make_adapter(timeout_s=0.5).run(task(tmp_path))
    assert result.status is RunStatus.TIMED_OUT
    assert time.monotonic() - start < 5
    assert result.exit_code is not None and result.exit_code < 0  # killed by a signal
    assert "timeout" in (result.error_details or "")
    assert result.session_id == "fake-session-0001"


def test_task_timeout_overrides_config(tmp_path: Path, scenario) -> None:
    scenario("hang")
    result = make_adapter(timeout_s=30).run(task(tmp_path, timeout_s=0.3))
    assert result.status is RunStatus.TIMED_OUT
    assert result.duration_s < 5


def test_sigterm_ignored_escalates_to_sigkill(tmp_path: Path, scenario) -> None:
    scenario("hang_ignore_term")
    start = time.monotonic()
    result = make_adapter(timeout_s=0.5, kill_grace_s=0.5).run(task(tmp_path))
    assert result.status is RunStatus.TIMED_OUT
    assert result.exit_code == -9
    assert time.monotonic() - start < 5


def test_timeout_kills_descendants(tmp_path: Path, scenario, monkeypatch) -> None:
    scenario("grandchild")
    pidfile = tmp_path / "pid"
    monkeypatch.setenv("FAKE_CLAUDE_PIDFILE", str(pidfile))
    result = make_adapter(timeout_s=1.0).run(task(tmp_path))
    assert result.status is RunStatus.TIMED_OUT
    grandchild = int(pidfile.read_text())
    deadline = time.monotonic() + 3
    while pid_alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not pid_alive(grandchild)


def test_cancellation(tmp_path: Path, scenario) -> None:
    scenario("hang")
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    result = make_adapter(timeout_s=30).run(task(tmp_path), cancel=cancel)
    assert result.status is RunStatus.CANCELLED
    assert result.duration_s < 5


def test_leftover_child_holding_pipes_does_not_hang(tmp_path: Path, scenario) -> None:
    scenario("leftover_child")
    start = time.monotonic()
    result = make_adapter().run(task(tmp_path))
    assert result.status is RunStatus.SUCCEEDED
    assert time.monotonic() - start < 8


def test_event_cap(tmp_path: Path, scenario) -> None:
    scenario("flood")
    result = make_adapter(max_events=10).run(task(tmp_path))
    assert result.status is RunStatus.SUCCEEDED  # result is still read after the cap
    assert len(result.events) == 10
    assert result.events_dropped == 42  # init + 50 assistant + result = 52


def test_large_event_payload_omitted(tmp_path: Path, scenario) -> None:
    scenario("big_event")
    result = make_adapter(max_stored_event_bytes=1024).run(task(tmp_path))
    assert result.status is RunStatus.SUCCEEDED
    big = result.events[1]
    assert big.type == "assistant"
    assert big.payload_omitted is True
    assert big.data is None


def test_oversized_line_discarded(tmp_path: Path, scenario) -> None:
    scenario("huge_line")
    result = make_adapter(max_line_bytes=10_000).run(task(tmp_path))
    assert result.status is RunStatus.SUCCEEDED
    assert any("exceeded" in (e.parse_error or "") for e in result.events)
    assert result.events[-1].type == "result"


def test_result_text_truncated(tmp_path: Path, scenario) -> None:
    scenario("big_result")
    result = make_adapter(max_result_chars=100).run(task(tmp_path))
    assert result.result_text == "r" * 100
    assert result.result_text_truncated is True


def test_stderr_is_tail_capped(tmp_path: Path, scenario) -> None:
    scenario("stderr_flood")
    result = make_adapter(max_stderr_bytes=1000).run(task(tmp_path))
    assert len(result.stderr_tail) == 1000
    assert result.stderr_tail.endswith("TAIL")


def test_missing_binary_is_launch_error(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(AdapterConfig(claude_command=["/nonexistent/claude"]))
    result = adapter.run(task(tmp_path))
    assert result.status is RunStatus.LAUNCH_ERROR
    assert result.exit_code is None
    assert "could not launch" in (result.error_details or "")


def test_invalid_workspace_is_launch_error(tmp_path: Path) -> None:
    result = make_adapter().run(task(tmp_path / "missing"))
    assert result.status is RunStatus.LAUNCH_ERROR
    assert "not a directory" in (result.error_details or "")


def test_callback_errors_do_not_break_run(tmp_path: Path, scenario) -> None:
    scenario("success")

    def boom(_event: RunEvent) -> None:
        raise RuntimeError("callback failure")

    result = make_adapter().run(task(tmp_path), on_event=boom)
    assert result.status is RunStatus.SUCCEEDED


def test_result_serialises_to_json(tmp_path: Path, scenario) -> None:
    scenario("success")
    result = make_adapter().run(task(tmp_path))
    payload = json.loads(result.model_dump_json())
    assert payload["status"] == "succeeded"
    assert payload["runtime"] == "claude_code"
