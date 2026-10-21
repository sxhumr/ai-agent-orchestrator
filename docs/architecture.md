# Architecture

This document covers the current state as of Milestone 2 plus the GUI. `forgeflow_project_spec.md` §4 describes the full target architecture.

## Modules

```
backend/src/forgeflow/
├── config.py               AdapterConfig: limits and permission policy
├── models/
│   ├── execution.py        TaskSpec, RunEvent, RunStatus, RunResult (runtime I/O)
│   └── requirements.py     Project, Brief, Requirement, OpenItem, AgentRunRecord
├── runtime/claude_code.py  RuntimeAdapter protocol + ClaudeCodeAdapter
├── store/db.py             SQLite Store, migrations, transactions
├── api/app.py              FastAPI app for the GUI (thin layer over store and analyst)
├── analysis/
│   ├── schema.py           AnalysisOutput: the structured output the analyst must return
│   ├── analyst.py          analyse_brief(): run → validate → map → persist
│   └── export.py           Markdown/JSON export
└── cli.py                  `forgeflow run | serve | project | brief | requirements | questions`

frontend/                   Next.js 16 (App Router, Cache Components) + Tailwind v4
├── src/app/                routes: /, /projects/[name]/{,brief,requirements,requirements/[key],questions}
├── src/components/ui/      design-system primitives (no component libraries)
├── src/components/projects/ feature components (shell, analysis panel, criteria editor…)
└── src/lib/api/            typed fetch client + TanStack Query hooks
```

Dependencies point one way: (`cli`, `api`) → `analysis` → (`runtime`, `store`) → `models`. The core never imports the API or the GUI, and everything the GUI can do is also available from the CLI.

## GUI and API

- **Talking to the API:** the GUI is a client-rendered Next.js app that calls the API directly through CORS. It doesn't go through a Next proxy, which would time out on minute-long analyses.
- **Server state:** state lives in TanStack Query. Any write invalidates every query for that project.
- **No in-memory job queue:** `POST /analysis` holds the request open until the run finishes. The API keeps an in-process "running" set only to refuse concurrent runs and to tell other tabs a run is in progress. Those tabs poll `GET /projects/{name}` every 3s while `analysis_running` is true. The persisted agent run record stays the source of truth.
- **Errors:** `NotFoundError` maps to 404, `ConflictError` to 409, other `StoreError`s to 400, and `AnalysisError` and domain validation errors to 422 (with `run_id` when a run was recorded).
- **Cache Components:** project routes read `params` through `useParams`, under a `Suspense` boundary in `projects/[name]/layout.tsx`.
- **No theme flash:** the theme is set by an inline `<head>` script so the first paint is correct. In this Next version a `beforeInteractive` `<Script>` is queued rather than inlined, so it can't be used for this.

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
