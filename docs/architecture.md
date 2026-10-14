# Architecture

This document covers the current state as of Milestone 2. `forgeflow_project_spec.md` §4 describes the full target architecture.

## Modules

```
forgeflow/
├── config.py               AdapterConfig: limits and permission policy
├── models/
│   ├── execution.py        TaskSpec, RunEvent, RunStatus, RunResult (runtime I/O)
│   └── requirements.py     Project, Brief, Requirement, OpenItem, AgentRunRecord
├── runtime/claude_code.py  RuntimeAdapter protocol + ClaudeCodeAdapter
├── store/db.py             SQLite Store, migrations, transactions
├── analysis/
│   ├── schema.py           AnalysisOutput: the structured output the analyst must return
│   ├── analyst.py          analyse_brief(): run → validate → map → persist
│   └── export.py           Markdown/JSON export
└── cli.py                  `forgeflow run | project | brief | requirements | questions`
```

Dependencies point one way: `cli` → `analysis` → (`runtime`, `store`) → `models`. The orchestration core never imports the GUI, and the GUI doesn't exist yet.

## Adapter boundary

Callers talk only to `RuntimeAdapter.run(TaskSpec) -> RunResult`. Everything specific to Claude Code stays in `ClaudeCodeAdapter`: argv, the stream-json schema, status mapping and process groups. The analyst depends on the protocol, which is why its unit tests can use a `FakeAdapter`.

Run lifecycle:
1. Validate the workspace.
2. Launch the CLI in its own process group.
3. Three daemon threads handle stdin, stdout (parsed within caps) and stderr (tail kept).
4. The main thread polls for exit, cancel and the deadline. On cancel or timeout it sends SIGTERM to the group, waits, then sends SIGKILL.
5. The pipes are drained and the status is classified.

## Requirements analysis (Milestone 2)

```
Brief vN ──► ClaudeCodeAdapter (tools="", --json-schema, empty temp cwd)
                 │ structured_output
                 ▼
         AnalysisOutput (Pydantic: extra=forbid, unique refs, no dangling refs)
                 │
                 ▼  one transaction
  Requirements REQ-nnn v1 ── source: brief id/version + quote (verified) ── run id
  OpenItems    Q-nnn ─────── links via open_item_requirements (FK-checked)
  AgentRun record (always written, even when output is rejected)
```

AI proposes and deterministic code decides. The model never chooses persisted IDs or keys and never writes rows. The model's local `ref`s are resolved to real IDs by ForgeFlow, and quote verification is plain string matching.

## Persistence

- One SQLite file. WAL mode, `foreign_keys=ON`, and transactions are explicit through `Store.transaction()`. Nested calls join the outer transaction.
- Each row keeps a few indexed or constrained columns, plus the full Pydantic model as JSON in `data`.
- `requirements` holds identity (ID and key). `requirement_versions` is append-only, one row per version.
- Open-item links live in `open_item_requirements` so they are reference-checked. They aren't stored inside the JSON blob.
- Migrations are an ordered list of statement tuples applied under `PRAGMA user_version`. A database newer than the code is refused.

## Decisions

- [0001: Headless stream-json integration](decisions/0001-claude-code-headless-stream-json.md)
- [0002: Central SQLite store with JSON model columns](decisions/0002-sqlite-store.md)
- [0003: Analyst uses schema-constrained output with deterministic post-validation](decisions/0003-analyst-structured-output.md)
