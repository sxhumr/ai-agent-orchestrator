# Runtime adapter

How ForgeFlow runs Claude Code: the `forgeflow run` command, the Python adapter API, the exact CLI invocation, the limits on each run, and what has been verified against the real CLI. This was the README's reference section until Milestone 2; the architecture overview is in [`architecture.md`](architecture.md) and the decision record in [`decisions/0001-claude-code-headless-stream-json.md`](decisions/0001-claude-code-headless-stream-json.md).

## Running a single task

```bash
uv run forgeflow run --cwd /path/to/repo \
  --prompt "Add a hello() function to app.py" \
  --allowed-tools Read,Edit \
  --max-budget-usd 0.50 --timeout 300
```

The command streams event types to stderr and prints a JSON `RunResult` to stdout. It exits with 0 only when the status is `succeeded`. Ctrl-C cancels the run cleanly. Other flags: `--prompt-file`, `--disallowed-tools`, `--model`, `--resume <session-id>`, `--permission-mode`, `--events` (include raw events) and `--quiet`.

## Adapter from Python

```python
from pathlib import Path
from forgeflow.config import AdapterConfig
from forgeflow.models import TaskSpec, RunStatus
from forgeflow.runtime import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter(AdapterConfig(timeout_s=300))
result = adapter.run(
    TaskSpec(prompt="...", workspace=Path("repo"), allowed_tools=["Read", "Edit"]),
    cancel=None,  # optional threading.Event; set it to stop the run
    on_event=print,  # optional live callback, called with each RunEvent
)
if result.status is RunStatus.SUCCEEDED and not result.permission_denials:
    ...
```

## Adapter interface

`RuntimeAdapter.run(task, *, cancel, on_event) -> RunResult` lives in `src/forgeflow/runtime/claude_code.py`. Everything specific to the CLI stays inside `ClaudeCodeAdapter`.

| `RunStatus` | Meaning |
|---|---|
| `succeeded` | Exit code 0, a `result` event arrived with `subtype == "success"`, and `is_error` is false |
| `failed` | The exit code was non-zero, or the result event reported an error such as `error_max_budget_usd` |
| `timed_out` | The wall-clock limit was hit and the process group was stopped |
| `cancelled` | The `cancel` event was set and the process group was stopped |
| `launch_error` | The binary is missing or not executable, or the workspace isn't a directory |
| `protocol_error` | The process exited 0 but never emitted a `result` event |

Status always comes from the exit code and the structured `result` event, never from output text. `RunResult` also records the session ID, argv (the prompt is not included), timings, cost, turns, final result text, permission denials, the stderr tail and the stored events.

### How a run is invoked

```
claude -p --output-format stream-json --verbose \
  --permission-mode dontAsk --permission-prompts none \
  --session-id <uuid> | --resume <id> \
  [--tools ...] [--allowedTools ...] [--disallowedTools ...] [--model ...]
  [--max-budget-usd ...] [--append-system-prompt ...] [--json-schema ...]
```

- The prompt goes in on **stdin**, so it has no argv length limit and doesn't show up in `ps`.
- `dontAsk` together with `--permission-prompts none` gives least privilege. Only the tools in `allowed_tools` can run, and anything else is denied automatically, so the run never blocks waiting for a human.
- The process starts in its own **process group**. Timeout and cancel send SIGTERM to the group, wait `kill_grace_s`, then send SIGKILL, so descendants are stopped too. If a leftover background process keeps the output pipes open after the CLI exits, the group gets SIGKILL.

### Bounds (`AdapterConfig`)

| Setting | Default | What it limits |
|---|---|---|
| `timeout_s` | 600 | Wall-clock time per run. `TaskSpec.timeout_s` overrides it for one task. |
| `kill_grace_s` | 5 | Delay between SIGTERM and SIGKILL |
| `max_events` | 1000 | Events stored per run. Extra events are counted in `events_dropped`, and the final result is still read. |
| `max_line_bytes` | 8 MiB | Longest stdout line that gets parsed. Longer lines are discarded and recorded as a parse error. |
| `max_stored_event_bytes` | 64 KiB | Events larger than this are stored without their payload |
| `max_stderr_bytes` | 64 KiB | Tail of stderr that's kept |
| `max_result_chars` | 20 000 | Final result text that's kept |

## Verified behaviour vs assumptions

These were **observed against Claude Code 2.1.299** on 2026-10-14:
- stream-json emits `system/init`, then `assistant`, `user`, `rate_limit_event` and `system/*` events, and finally a `result` event with `subtype`, `is_error`, `total_cost_usd`, `num_turns`, `result`, `session_id` and `permission_denials`.
- The prompt is accepted on stdin when no positional prompt is given.
- A session ID set with `--session-id` is the one the CLI reports.
- An invalid flag exits 1 with the error on stderr.
- `--json-schema` puts the validated object in `result.structured_output`, and this works even with `--tools ""`. The schema Pydantic generates, including `$defs`/`$ref`, is accepted.
- **When a tool is blocked by permissions, the run still reports `success`.** The CLI emits `system/permission_denied` events and fills `permission_denials`, and the model explains the problem in its result text. The adapter records the denials, but **callers must check `permission_denials`** and not rely on `status` alone. The orchestration layer will decide policy for this in Milestone 4.

These are **not yet verified**:
- `--resume` with stdin input in a real multi-turn workflow. The flag is passed correctly, but no live test covers it yet.
- What exit code and result subtype the CLI uses when `--max-budget-usd` is exceeded. It's handled generically as `failed` through `is_error` or a non-success subtype.
- Whether SIGTERM lets the CLI flush its session transcript before exiting.
- Whether the event schema stays stable across CLI versions. The adapter reads only `type`, `subtype`, `session_id` and the result fields listed above, and ignores everything else.

