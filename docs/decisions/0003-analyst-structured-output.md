# 0003: Analyst uses schema-constrained output with deterministic post-validation

- Status: accepted
- Date: 2026-10-14

## Context

The analyst turns free text into records ForgeFlow will rely on for planning and traceability. The spec requires AI output to be validated with Pydantic and treated as a proposal, and it requires source traceability to be preserved.

## Decision

- **The JSON Schema comes from `AnalysisOutput`** and is passed through `--json-schema`. The CLI then constrains the final answer to that schema, and it arrives in `result.structured_output` (verified with Claude Code 2.1.299).
- **The output is validated again with Pydantic** (`extra="forbid"`, enums, non-empty requirement list, unique `ref`s, no dangling `related_refs`). The schema and the validator could drift apart, and that must not let bad data through.
- **The model uses local refs (`R1`).** ForgeFlow assigns the persisted IDs and keys and resolves the links.
- **Every requirement carries a `source_quote`,** which is verified against the brief by normalised substring matching, never by asking a model. A failed match is a visible flag, not an error, because a paraphrase can still be a valid requirement.
- **The analyst runs with `--tools ""` in an empty temporary directory,** and the brief is wrapped and declared to be data. It needs no tools, and removing them limits what prompt injection in a brief could do.
- **The agent run is recorded whether or not its output is accepted,** so failures and their cost stay visible.

## Consequences

- Re-running analysis can produce different requirements. Generation is therefore one-shot per project for now, and incremental re-analysis waits for Milestone 6.
- There's no automatic retry when output is invalid. The developer re-runs `generate`, and the failed attempt stays recorded.
