# ForgeFlow

ForgeFlow is a local-first orchestrator. It takes a project from a business brief to approved requirements, an approved plan, code and independent verification, with Claude Code CLI as the coding runtime. `forgeflow_project_spec.md` has the full specification.

**Status: Milestones 1 and 2 are done, and a GUI covers them.**
- **Milestone 1 (Claude Code adapter):** runs one bounded Claude Code task and records how it ended.
- **Milestone 2 (structured requirements):** turns a business brief into persisted, versioned requirements and open questions, each traceable back to the brief.
- **GUI:** a local web app for everything in Milestone 2.

Planning, approvals and implementation come in later milestones.

## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), and Claude Code CLI on `PATH` and already authenticated. Development used 2.1.299.

```bash
uv sync
```

## GUI

Two processes, both local only:

```bash
uv run forgeflow serve                 # API on http://127.0.0.1:8765
cd gui && npm install && npm run dev   # GUI on http://localhost:3000
```

- If port 3000 is taken, run the GUI with `npm run dev -- -p 3100` and allow that origin on the API with `uv run forgeflow serve --gui-origin http://localhost:3100`.
- The GUI reads `NEXT_PUBLIC_API_URL`, which defaults to `http://127.0.0.1:8765`.

**Screens:** projects, a project overview (next step, stats, agent runs and their cost), brief versions and analysis, requirements (filter, add, then open one to accept, reject or edit it with version history and source quote), and open questions (answer or dismiss).

**API safety.** The API has no login and can start paid Claude Code runs, so:
- `serve` refuses any host other than loopback.
- Requests whose `Host` header isn't localhost are rejected, which guards against DNS rebinding.
- CORS only allows the configured GUI origins.
- Only one analysis can run per project at a time. A second request gets `409`.

The GUI follows the shared design system in `~/Desktop/UI-DESIGN-GUIDELINES.md`. The tokens are in `gui/src/app/globals.css` and the primitives in `gui/src/components/ui/`. There are no component or icon libraries.

## Usage

### Requirements workflow (Milestone 2)

```bash
uv run forgeflow project create shop --root ~/code/shop --description "Repair bookings"
uv run forgeflow brief add shop --file brief.md        # each add creates a new brief version
uv run forgeflow requirements generate shop             # Claude Code analyses the latest brief
uv run forgeflow questions list shop                    # open questions, ambiguities, assumptions
uv run forgeflow questions resolve shop Q-003 --answer "Owner and two staff"
uv run forgeflow req edit shop REQ-002 --status accepted --criterion "..." --note "Q-003"
uv run forgeflow req show shop REQ-002                  # details, source quote, related questions
uv run forgeflow req history shop REQ-002               # every version, who changed it and why
uv run forgeflow req add shop --title "Audit log" --description "..." --criterion "..."
uv run forgeflow req export shop --out docs/requirements   # requirements.md + requirements.json
uv run forgeflow project show shop
```

How generation works:
- **The analyst runs with no tools** (`--tools ""`) in an empty temporary directory. It can't read or change your files. It only sees the brief, which the prompt marks as data, not instructions.
- **Output is constrained and then re-validated.** A JSON Schema built from `forgeflow.analysis.schema.AnalysisOutput` is passed through `--json-schema`, and the result is validated again with Pydantic. Duplicate or dangling requirement references are rejected. Invalid output is recorded against the agent run, and nothing is persisted.
- **ForgeFlow assigns every key**, never the model: `REQ-001`, `Q-001` and `AC-1`. Everything from one analysis is written in a single transaction.
- **Source quotes are checked deterministically against the brief.** Matching ignores case, whitespace and typographic quotes, and `...` counts as a gap. Requirements whose quote is missing or wasn't found are flagged `?src` in listings and reported after generation.
- **Versions are never overwritten.** Each requirement edit appends a new version with an optional change note, and each `brief add` creates a new brief version. Every requirement records the brief version and the agent run that produced it.
- **`generate` refuses if the project already has requirements.** Re-analysing after a brief change is Milestone 6 (change impact).

**Storage:** everything lives in one SQLite database at `$FORGEFLOW_HOME/forgeflow.db`, which defaults to `~/.local/share/forgeflow/forgeflow.db`. Pass `--db PATH` to use a different one. The schema is upgraded automatically through numbered migrations (`PRAGMA user_version`). Use `req export` for human-readable copies.

### Running a single task (Milestone 1)

```bash
uv run forgeflow run --cwd /path/to/repo \
  --prompt "Add a hello() function to app.py" \
  --allowed-tools Read,Edit \
  --max-budget-usd 0.50 --timeout 300
```

The command streams event types to stderr and prints a JSON `RunResult` to stdout. It exits with 0 only when the status is `succeeded`. Ctrl-C cancels the run cleanly. Other flags: `--prompt-file`, `--disallowed-tools`, `--model`, `--resume <session-id>`, `--permission-mode`, `--events` (include raw events) and `--quiet`.

### Adapter from Python

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

## Development

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
(cd gui && npx tsc --noEmit && npm run lint && npm run build)
uv run pytest tests/unit                          # deterministic; uses tests/unit/fake_claude.py
FORGEFLOW_LIVE=1 uv run pytest tests/integration  # real CLI; three small paid calls (≈ $0.30 total)
```

## Limitations

- Adapter runs started with `forgeflow run` aren't persisted. Analyst runs are recorded in `agent_runs`, without their raw events.
- Project status is set when requirements are generated (`AWAITING_CLARIFICATION` or `REQUIREMENTS_REVIEW`) but doesn't move after that. The enforced state machine and the approval of the requirements baseline arrive in Milestone 3.
- `req edit --criterion` replaces all acceptance criteria. Repeat the flag for each criterion you want to keep.
- POSIX only, because it relies on process groups (`os.killpg`).
- The adapter doesn't inspect or restrict what allowed tools do inside the workspace. That's down to Claude Code's permission system and the `allowed_tools` you pass.
- The environment is inherited from the parent process. Credentials aren't written to `RunResult`, but they are visible to the CLI.

## Next steps

Milestone 3 covers planning and approval: architecture proposals and decisions, implementation tasks with dependency edges (NetworkX cycle detection and ordering), an explicit approval gate, approval records, workflow events and the enforced workflow state machine.
