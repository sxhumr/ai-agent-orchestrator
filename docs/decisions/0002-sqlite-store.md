# 0002: Central SQLite store with JSON model columns

- Status: accepted
- Date: 2026-10-14

## Context

Milestone 2 needs projects, briefs, requirement versions, open items and agent runs to persist across restarts. The spec calls for SQLite, migrations from the start, reference validation and inspectable artefacts.

## Decision

- **One database per ForgeFlow installation** at `$FORGEFLOW_HOME/forgeflow.db`, defaulting to `~/.local/share/forgeflow/`. It is not stored inside each target repository. That keeps the developer's repos free of ForgeFlow state and lets a future GUI list every project.
- **Each table has a few relational columns plus a `data` JSON column** holding the full Pydantic model. The relational columns cover IDs, project, key, version, status and timestamps, and they carry the uniqueness and foreign-key constraints. Model fields can change without a migration for every field, while the relationships that matter stay enforced by SQLite.
- **Requirement history is append-only.** It's split into an identity table and an immutable version table.
- **Migrations live in an ordered list in code** and are tracked with `PRAGMA user_version`. Each migration runs in its own transaction.
- **Human-readable artefacts come from export** (`req export`), so the database stays the single source of truth.

## Consequences

- Querying by fields inside `data` needs `json_extract`. When a field becomes a frequent filter, it should be promoted to a column through a migration.
- Exported files can drift from the database if they're edited by hand. Import is not supported yet.
- A single file means no concurrent multi-user access. That's acceptable for a personal tool, and PostgreSQL remains the documented escape hatch.
