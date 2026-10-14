# Architecture

This document covers the current state as of Milestone 1. `forgeflow_project_spec.md` §4 describes the full target architecture.

## Modules

```
forgeflow/
├── config.py            AdapterConfig: limits and permission policy
├── models/execution.py  TaskSpec (input), RunEvent, RunStatus, RunResult (outcome)
├── runtime/claude_code.py
│                        RuntimeAdapter protocol + ClaudeCodeAdapter
└── cli.py               `forgeflow run`, a thin wrapper over the adapter
```

## Adapter boundary

The orchestration core, which isn't built yet, talks only to `RuntimeAdapter.run(TaskSpec) -> RunResult`. Everything specific to Claude Code stays in `ClaudeCodeAdapter`. That covers argv construction, the stream-json event schema, mapping exit codes and result events to `RunStatus`, and process-group handling. If the CLI changes or another runtime is added, only this module should need to change.

## Run lifecycle

1. Resolve and validate the workspace, then build argv. The prompt is not part of argv.
2. Launch the CLI as `Popen(start_new_session=True)`, which gives it its own process group.
3. Three daemon threads handle I/O: one writes the prompt to stdin and closes it, one parses stdout line by line within the line and event caps, and one keeps a capped tail of stderr.
4. The main thread polls for exit, the cancel event and the deadline. On cancel or timeout it sends SIGTERM to the group, waits the grace period, then sends SIGKILL.
5. After the CLI exits, the I/O threads get time to drain. If a descendant still holds the pipes, the group gets SIGKILL.
6. The status is classified (see README) and an immutable `RunResult` is returned.

## Decisions

- [0001: Headless stream-json integration](decisions/0001-claude-code-headless-stream-json.md)
