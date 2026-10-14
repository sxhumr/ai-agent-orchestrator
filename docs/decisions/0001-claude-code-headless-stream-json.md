# 0001: Integrate Claude Code through headless `-p` with stream-json

- Status: accepted
- Date: 2026-10-14

## Context

ForgeFlow needs to launch bounded coding tasks from Python and record their outcomes reliably. The spec forbids scraping terminal output when a machine-readable interface exists, and it requires timeouts, cancellation and bounded capture.

The options considered were:

1. **`claude -p --output-format stream-json`**, run as a subprocess. It's the supported CLI interface. It emits newline-delimited JSON events with a final `result` event, and supports `--session-id`/`--resume`, `--permission-mode`, `--permission-prompts none`, `--allowedTools` and `--max-budget-usd`.
2. **`--output-format json`**, which returns a single result object at the end. It's simpler, but it gives no live events, and a killed run yields no partial data at all.
3. **The Claude Agent SDK.** It offers a richer in-process API, including permission callbacks, but adds a dependency and another layer between ForgeFlow and the CLI that the spec names as the runtime.

## Decision

Use option 1. Send the prompt on stdin, use `dontAsk` with `--permission-prompts none` for least privilege so nothing can block on a prompt, and start each run in its own process group so timeout and cancel can stop every descendant.

## Consequences

- Live events are available for the GUI later, and timed-out or cancelled runs still keep the events they produced.
- Permission denials don't fail a run on the CLI side. Callers have to inspect `RunResult.permission_denials`.
- A future need for interactive permission approval, where a human approves a tool mid-run, would mean revisiting this. The likely routes are the Agent SDK's permission callback or `--permission-prompt-tool`.
- The approach is POSIX-only because of `os.killpg`.
