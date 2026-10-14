# ForgeFlow — Project Specification for a CLI Coding Agent

## 1. Project Overview

Build **ForgeFlow**, a local-first, GUI-enabled software development orchestrator that uses **Claude Code CLI** as its coding runtime.

The user provides business requirements. ForgeFlow works backwards from those requirements to plan the architecture and implementation, asks the developer to resolve ambiguity and approve important decisions, orchestrates coding work, and verifies the resulting software.

This is a personal developer tool, not a commercial SaaS product. Optimise for usefulness in a single developer's workflow, reliability, transparency, and extensibility. Do not add infrastructure or product features without a clear need.

### Core objective

Create a controlled workflow that takes a project from:

**Business brief → clarified requirements → approved architecture → dependency-aware implementation plan → code → independent verification → reviewed delivery**

The system must preserve traceability between business requirements, design decisions, implementation tasks, code changes, and acceptance tests.

### Key principle

ForgeFlow is an **engineering orchestration system with an AI interface**, not merely a collection of prompts. Use AI for interpretation, planning proposals, coding, and review; use deterministic software for state transitions, permission enforcement, dependency management, validation, and evidence tracking wherever possible.

---

## 2. Intended User Experience

The developer creates a project and supplies a business brief, existing documents, or rough notes.

ForgeFlow then:

1. Extracts and structures the requirements.
2. Identifies ambiguity, missing information, assumptions, and possible contradictions.
3. Asks the developer focused clarifying questions.
4. Produces acceptance criteria and non-functional requirements.
5. Proposes architecture options and explains their trade-offs.
6. Produces a dependency-aware implementation plan.
7. Presents the plan and consequential decisions for developer approval.
8. Executes approved tasks through Claude Code CLI.
9. Runs tests, static checks, and requirement-oriented verification.
10. Attempts bounded, targeted fixes when checks fail.
11. Reports completion, evidence, unresolved issues, and known limitations.
12. Supports requirement changes by identifying affected artefacts and proposing an incremental replan rather than regenerating everything.

The developer must be able to pause, resume, inspect, reject, edit, and approve the workflow.

Do not begin substantial implementation before the developer has approved the requirements and plan. Allow configurable approval policies later, but default to explicit approval for consequential decisions.

---

## 3. Proposed Technology Stack

Use this as the initial default stack. Prefer simple, well-supported components and avoid unnecessary abstraction.

### Backend and orchestration
- Python
- FastAPI for the local API
- Pydantic for typed, validated data models
- SQLite for local workflow state and metadata
- Markdown, JSON, and YAML for human-readable project artefacts where appropriate
- NetworkX initially for dependency graph operations; implement custom algorithms only when there is a clear reason
- pytest for testing
- Ruff for linting and formatting
- Type checking where practical

### GUI
- Next.js
- TypeScript
- Tailwind CSS
- A clean, developer-focused interface for requirements, architecture, task planning, approvals, execution, and review

The GUI is a local companion to the Python service. Do not require Vercel, Render, or cloud hosting for the MVP.

### Coding runtime
- Claude Code CLI, invoked through a supported programmatic interface where available
- Investigate the currently supported Claude Code CLI/headless execution, structured output, streaming/event formats, session continuation, and permission mechanisms before implementing the integration
- Do not depend on brittle terminal-output scraping if a supported machine-readable interface is available
- Do not assume every interactive CLI permission prompt can be surfaced or controlled externally; verify the actual integration capabilities

### Version control and execution
- Git
- Git worktrees or another isolated-workspace approach for independent tasks when multi-agent execution is added
- Subprocess management with timeouts, cancellation, exit-code handling, and bounded output capture
- Local test and lint commands, with an explicit allowlist/policy where appropriate

### Future extension points
- MCP server exposing reusable ForgeFlow capabilities to compatible clients
- Claude Code skills for guiding workflows
- PostgreSQL if local persistence eventually needs to support multiple users or larger workloads
- Optional hosted GUI/API, only if a real need emerges

Do not implement every extension point in the MVP.

---

## 4. System Architecture

Use clear module boundaries. Avoid an unnecessarily distributed architecture.

### A. GUI
Responsibilities:
- Create/open projects
- Edit business briefs and requirements
- Answer clarification questions
- Review architecture decisions
- View and edit the task dependency graph
- Approve/reject plans and actions
- Monitor task and agent status
- Inspect logs, diffs, tests, and verification evidence
- Pause, resume, cancel, or retry runs
- Review change-impact proposals

### B. FastAPI application
Responsibilities:
- Serve project and workflow APIs
- Validate incoming requests
- Expose workflow state and execution events
- Coordinate the GUI with the orchestration service
- Enforce access and approval checks within the local application

### C. Orchestration core
Responsibilities:
- Own the workflow state machine
- Persist state and events
- Schedule tasks when dependencies are satisfied
- Enforce approval gates and execution policies
- Launch and supervise Claude Code sessions
- Handle retries, timeouts, cancellation, and recoverable failures
- Coordinate verification and bounded repair loops
- Track traceability between requirements, decisions, tasks, and tests

Keep this core independent of the GUI so it can be tested and operated from the CLI.

### D. Requirement and planning engine
Responsibilities:
- Maintain structured requirement models
- Track assumptions, open questions, constraints, and decisions
- Detect duplicate or potentially contradictory requirements
- Build dependency graphs
- Validate task dependencies and detect cycles
- Generate valid task orderings
- Identify parallelisable work and critical paths where task-duration estimates exist
- Compute potential change impact
- Preserve valid decisions during incremental replanning

Use deterministic algorithms for graph correctness, cycle detection, scheduling constraints, and state validation. Use AI to propose interpretations and plans, not as the sole source of truth.

### E. Claude Code adapter
Responsibilities:
- Start coding sessions with bounded task instructions
- Supply approved context and artefacts
- Capture machine-readable output and session identifiers when supported
- Support resumption and cancellation where supported
- Record command outcomes and errors
- Apply execution timeouts and output limits
- Keep CLI-specific logic behind an adapter interface

Do not assume the Claude Code CLI has capabilities that have not been verified. Document any integration limitations.

### F. Verification engine
Responsibilities:
- Run approved tests, linting, type checks, and other configured validators
- Capture exit codes and useful output
- Map checks to acceptance criteria where possible
- Inspect changes against the approved task and architecture
- Produce verifiable findings rather than unsupported claims
- Request targeted fixes within a bounded retry budget
- Stop and escalate when validation continues to fail

### G. Persistence and project artefacts
Store:
- Projects and project configuration
- Requirement versions
- Open questions and assumptions
- Architecture decisions and their rationale
- Task graph and task states
- Approval records
- Agent runs and session metadata
- Validation results and evidence
- Change-impact analyses
- Workflow event history

Keep project artefacts inspectable and exportable. Prefer human-readable formats for requirements, decisions, plans, and reports. SQLite may store indexes, runtime state, and metadata.

---

## 5. Workflow State Machine

Implement explicit, validated state transitions. Suggested high-level states:

- `INITIALISING`
- `DISCOVERY`
- `AWAITING_CLARIFICATION`
- `REQUIREMENTS_REVIEW`
- `ARCHITECTURE_PLANNING`
- `AWAITING_PLAN_APPROVAL`
- `READY_TO_IMPLEMENT`
- `IMPLEMENTING`
- `VERIFYING`
- `REPAIRING`
- `AWAITING_DEVELOPER_DECISION`
- `COMPLETED`
- `BLOCKED`
- `CANCELLED`
- `FAILED`

Define legal transitions in code. Persist transitions and their timestamps. Invalid transitions must be rejected and tested.

Requirements:
- The workflow must be resumable after the application or machine restarts.
- A pause or cancellation must not corrupt project state.
- An agent must not bypass an approval gate by changing its own instructions.
- Failed stages must record their cause and provide a safe retry path where possible.
- Retries must be bounded and visible to the developer.
- Avoid duplicate execution when a task is retried or a request is repeated.

Do not use a long-running in-memory background task as the only record of workflow state.

---

## 6. Structured Data Model

Create typed, versioned models. Adapt details when implementation reveals a better design, but preserve the relationships below.

### Project
- `id`
- `name`
- `root_path`
- `description`
- `created_at`
- `updated_at`
- `status`
- `configuration`

### Requirement
- `id`
- `project_id`
- `title`
- `description`
- `requirement_type` (functional, non-functional, constraint, business goal)
- `priority`
- `source_reference`
- `acceptance_criteria`
- `status`
- `confidence` or uncertainty indicator where useful
- `version`
- `created_at`
- `updated_at`

### Assumption / Open Question
- `id`
- `project_id`
- `related_requirement_ids`
- `description`
- `kind` (assumption, open question, ambiguity, potential conflict)
- `impact`
- `status`
- `resolution`
- `resolved_by`
- `resolved_at`

### Architecture Decision
- `id`
- `project_id`
- `title`
- `context`
- `options_considered`
- `decision`
- `rationale`
- `trade_offs`
- `related_requirement_ids`
- `status` (proposed, approved, rejected, superseded)
- `version`

### Implementation Task
- `id`
- `project_id`
- `title`
- `description`
- `related_requirement_ids`
- `related_decision_ids`
- `depends_on_task_ids`
- `acceptance_checks`
- `assigned_role`
- `status`
- `workspace_or_worktree`
- `attempt_count`
- `created_at`
- `updated_at`

### Agent Run
- `id`
- `project_id`
- `task_id`
- `role`
- `runtime`
- `session_reference`
- `status`
- `started_at`
- `finished_at`
- `exit_code`
- `summary`
- `error_details`

### Approval
- `id`
- `project_id`
- `related_entity_type`
- `related_entity_id`
- `action`
- `reason`
- `status`
- `requested_at`
- `decided_at`
- `decision_note`

### Validation Result
- `id`
- `project_id`
- `task_id`
- `check_name`
- `command_or_method`
- `status`
- `exit_code`
- `summary`
- `evidence_reference`
- `created_at`

Use stable IDs. Validate references and prevent dangling relationships. Introduce schema migrations from the start, even if the initial SQLite schema is small.

---

## 7. Requirements-to-Implementation Traceability

This is a core feature, not an optional reporting enhancement.

Every implementation task should link to one or more requirements or explicitly be labelled as enabling/infrastructure work. Every requirement should have a visible status and, where relevant, links to:
- Acceptance criteria
- Architecture decisions
- Implementation tasks
- Tests or verification checks
- Evidence of successful verification

The GUI should make it easy to answer:
- Which requirements are not implemented?
- Which requirements are implemented but not verified?
- Which tests demonstrate that a requirement works?
- Which tasks have no clear connection to the approved scope?
- What will be affected if a requirement changes?

Never mark a requirement complete merely because an agent claims it has implemented it. Completion must depend on defined evidence and verification policy.

---

## 8. Architecture and Implementation Planning

The planning workflow must:
1. Review approved requirements and constraints.
2. Identify unresolved questions that materially affect architecture.
3. Propose one or more viable architectures when meaningful.
4. Explain trade-offs in terms of the stated requirements.
5. Identify data entities, APIs, components, security boundaries, and integrations as applicable.
6. Record important decisions and their rationale.
7. Break work into tasks small enough to implement and verify.
8. Define dependencies between tasks.
9. Identify tasks that can safely run in parallel.
10. Define acceptance checks for tasks and requirements.
11. Present the plan for developer review.

Avoid false precision. Do not invent exact delivery estimates or claim an architecture is optimal without stated assumptions and criteria.

For the MVP, a modular monolith is the default unless the requirements justify something else. Do not introduce microservices merely to make the generated architecture look sophisticated.

---

## 9. Agent Roles and Execution Strategy

Start with a small number of roles:

### Planner / Requirements Analyst
Produces structured requirements, questions, assumptions, and acceptance criteria.

### Architect
Proposes technical design and records decisions.

### Implementer
Implements one approved, bounded task at a time.

### Reviewer
Reviews changes against the task, approved design, and relevant requirements. It should be independent of the implementation's success claims.

### QA / Verification
Runs deterministic checks and validates acceptance criteria where possible.

Initially, roles may use the same underlying model. Separate roles by responsibility and permissions, not merely by model name.

### Execution rules
- Begin with one implementation agent and one reviewer/verification path.
- Add parallel implementation only after single-agent execution is reliable.
- Parallel tasks must have explicit dependency rules and isolated workspaces.
- Do not let agents independently edit shared files without coordination.
- Integrate changes only after conflict checks and required validation.
- Do not assume an additional agent improves quality; measure it.
- Keep task context limited to relevant requirements, decisions, files, and interfaces.

---

## 10. Developer Approvals and Permissions

Make approval policies explicit and enforce them in the orchestration layer.

Require approval by default for:
- Approving the final requirements baseline
- Approving architecture and consequential design decisions
- Starting implementation against a plan
- Installing new skills or other third-party capabilities
- Adding dependencies or changing major versions where the policy requires it
- Running destructive commands or modifying files outside the approved project scope
- Accessing secrets or external services
- Performing network actions beyond the configured policy
- Changing infrastructure or deploying to production
- Merging significant or conflicting agent changes

Provide:
- A concise explanation of why approval is requested
- The exact action and its scope
- Relevant diff/configuration/source information
- Approve, reject, and optionally edit/revise actions
- An auditable decision record

Never let an agent approve its own request or expand its own permissions. Prefer least privilege. Do not store secrets in project artefacts, logs, prompts, or source control.

For third-party skills, display the source and relevant contents/metadata before installation when possible. Treat skill instructions as untrusted input and do not execute arbitrary install scripts without appropriate review and approval.

---

## 11. Testing and Verification Loop

Implement a bounded loop:

1. Run the relevant deterministic checks.
2. Capture results and evidence.
3. Compare outcomes against task acceptance checks.
4. If a check fails, classify the failure and provide relevant context.
5. Ask the implementer for a targeted fix when appropriate.
6. Re-run the failed checks and the necessary regression suite.
7. After the configured retry limit, stop and request developer intervention.

Use configurable limits for:
- Repair attempts
- Wall-clock execution time
- Model/tool calls
- Output size
- Parallel tasks
- Resource consumption where feasible

Do not allow infinite self-repair loops. Do not allow the same agent to be the sole authority for implementing, validating, and approving its own work.

### Initial validation tools
- pytest
- Ruff
- Type checks where configured
- Project-specific test commands
- Git diff and whitespace checks
- Dependency and configuration checks where appropriate

Tests and static analysis are evidence, not proof of total correctness. Clearly report unverified requirements and known gaps.

---

## 12. Change Impact and Incremental Replanning

This is a differentiating capability and should be developed after the first end-to-end workflow works.

When a requirement changes:
1. Version the changed requirement.
2. Identify directly linked architecture decisions, tasks, interfaces, and tests.
3. Traverse dependency relationships to find potentially affected downstream artefacts.
4. Ask AI to assess semantic impacts not represented in the graph.
5. Distinguish confirmed impacts from hypotheses.
6. Preserve unaffected decisions and completed work where valid.
7. Propose a revised plan and explain what changed.
8. Require approval for consequential architectural changes.
9. Re-run relevant validation after implementation.

Do not claim that graph reachability alone captures every semantic dependency. Combine deterministic graph traversal with explicit AI analysis and developer review.

Track unnecessary plan churn as a quality metric.

---

## 13. GUI Requirements

The GUI should be useful, not decorative. Prioritise these views:

### Project overview
- Current workflow state
- Progress by requirements and tasks
- Blockers and pending approvals
- Latest validation results

### Requirements
- Business brief
- Structured requirement list
- Clarifying questions
- Assumptions and conflicts
- Acceptance criteria
- Requirement version history

### Architecture
- Architecture proposal and decisions
- Component relationships
- Data model and API contracts where applicable
- Trade-offs and approval status

### Planning
- Task list and dependency graph
- Task status and dependencies
- Parallelisable work
- Requirement/task traceability

### Execution
- Agent role and current task
- Session/run status
- Live events and relevant output
- Current diffs and files changed
- Pause, resume, cancel, and retry controls

### Review and verification
- Test results and logs
- Review findings
- Requirement coverage
- Approval queue
- Unresolved failures and known limitations

Use streaming updates (for example, Server-Sent Events) if useful, but ensure persisted events are the source of truth so reconnecting to the GUI does not lose state.

---

## 14. Security and Reliability

Even though ForgeFlow is a personal local tool, it can execute code and access a developer's files. Treat execution safety seriously.

- Restrict execution to the configured project workspace by default.
- Resolve and validate paths to prevent path traversal and unintended writes.
- Use subprocess timeouts and safe cancellation.
- Capture exit codes; do not infer success from output text alone.
- Keep credentials out of logs and persisted prompts.
- Do not automatically run untrusted generated scripts with elevated permissions.
- Do not automatically install recommended skills or dependencies without the required approval.
- Keep a record of commands and actions taken by agents.
- Handle malformed model output and interrupted sessions.
- Persist state before and after consequential transitions.
- Make retries idempotent where possible.
- Use bounded retries and explicit failure states.
- Validate all model-generated structured data with Pydantic.
- Treat AI-generated plans and findings as proposals until validated or approved.
- Ensure the GUI cannot bypass backend permission enforcement.

---

## 15. Evaluation and Success Metrics

Do not evaluate the project solely by whether it can generate code.

Create a small benchmark of representative projects with known requirements and acceptance tests. Compare ForgeFlow with a baseline workflow where practical.

Track:
- Acceptance-test pass rate
- Requirements implemented and verified
- Regression count
- Defects caught before delivery
- Unnecessary or out-of-scope changes
- Number of human interventions
- Time to a verified result
- Model/tool calls and estimated cost where available
- Repair attempts and repair success rate
- Plan churn after requirement changes
- Correctness of dependency ordering
- False positives in review findings

Keep the benchmark reproducible. Record model/runtime versions, project inputs, configuration, and test results. Do not claim the workflow is better than a baseline without measurements.

---

## 16. MVP Scope

Build in this order.

### Milestone 1 — Prove the Claude Code adapter
- Inspect the installed/current Claude Code CLI capabilities and supported programmatic invocation.
- Implement a small Python adapter that launches a bounded task.
- Capture exit status, supported structured output/events, session identifiers, errors, and timing.
- Add timeout and cancellation handling.
- Test against a small temporary repository.
- Document unsupported or uncertain capabilities.

**Exit criterion:** ForgeFlow can run a simple bounded coding task and reliably record the outcome.

### Milestone 2 — Structured requirements
- Create the project and requirement models.
- Ingest a business brief.
- Generate structured requirements, questions, assumptions, and acceptance criteria.
- Validate AI output with Pydantic.
- Persist requirements and version changes.
- Add unit tests with mocked model output.

**Exit criterion:** A brief becomes editable, persisted, structured requirements without losing source traceability.

### Milestone 3 — Plan and approval
- Generate an architecture proposal and decisions.
- Produce implementation tasks and dependency edges.
- Detect dependency cycles and validate task ordering.
- Add an explicit approval gate.
- Persist approval records and workflow events.

**Exit criterion:** No coding starts until the required plan approval is recorded.

### Milestone 4 — Single-agent implementation and verification
- Execute one approved task at a time through the Claude Code adapter.
- Run configured tests and static checks.
- Record diffs and verification evidence.
- Add a bounded repair loop.
- Implement pause/resume and failure handling.

**Exit criterion:** The system can take a small project from approved plan to a verified result or a clear, recoverable failure state.

### Milestone 5 — GUI vertical slice
- Build project overview, requirements, plan approval, execution, and verification views.
- Connect to the local FastAPI service.
- Display persisted events and current state.
- Support approval, pause, resume, and cancellation.

**Exit criterion:** A developer can complete the MVP workflow through the GUI without losing visibility into the underlying actions.

### Milestone 6 — Change impact
- Version requirements and decisions.
- Identify affected artefacts through traceability and graph traversal.
- Add AI semantic impact analysis.
- Propose incremental replanning.
- Add tests for changed and unaffected requirements.

**Exit criterion:** A requirement change produces a reviewable impact report and revised plan without blindly rebuilding everything.

### Later milestone — Multi-agent execution
Only after the above is reliable:
- Add isolated Git worktrees
- Schedule independent tasks in parallel
- Detect file and interface conflicts
- Validate integration
- Add independent code review
- Measure quality and time against sequential execution

Do not begin with multi-agent parallel coding. First establish that the state model, single-agent execution, and verification loop are trustworthy.

---

## 17. Engineering Standards for the Coding Agent

When implementing ForgeFlow:

1. Inspect the repository and current environment before changing anything.
2. If the repository already contains code, understand its structure and tests before proposing broad refactors.
3. Write a short implementation plan for each milestone.
4. Work in small, reviewable increments.
5. Prefer typed interfaces and clear module boundaries.
6. Add tests alongside functionality.
7. Run relevant tests and linting after each meaningful change.
8. Do not claim tests passed unless they were actually run and their exit status checked.
9. Do not invent Claude Code CLI capabilities; inspect the installed version and current supported interface.
10. Keep secrets, credentials, and private work-project code out of the repository.
11. Do not copy proprietary code or internal artefacts from the user's employer into this project.
12. Document meaningful architectural decisions and trade-offs.
13. Update documentation when behaviour or setup changes.
14. Avoid premature abstractions and speculative features.
15. Do not implement the entire roadmap in one pass.
16. If blocked by an ambiguity or a consequential decision, explain the issue and ask the developer instead of silently guessing.
17. Never install skills, dependencies, or external tools without following the project's approval policy.
18. Keep the system usable from the CLI even after the GUI exists.

---

## 18. First Task for the Coding Agent

**Do not start by implementing the entire application.**

Begin with a repository/environment assessment and a short technical investigation.

1. Inspect the current repository, available tooling, and existing project conventions.
2. Determine whether this is a new repository or an existing codebase.
3. Inspect the installed Claude Code CLI version and its supported programmatic execution, structured output, session management, and permission controls. Verify against current official documentation if internet access is available.
4. Identify the smallest reliable integration path for a Python process to launch a bounded Claude Code task, observe completion, and record the result.
5. Propose the initial directory structure and minimal architecture.
6. Implement **Milestone 1 only**, unless the developer explicitly asks for more.
7. Add automated tests using mocks where appropriate and a safe integration test where feasible.
8. Run the tests and lint checks; report exact outcomes.
9. Document the adapter interface, setup instructions, limitations, and next steps.
10. Present a concise summary of files changed, decisions made, checks run, and anything requiring developer input.

### Suggested initial repository layout

Adapt to the existing repository if one exists; do not restructure unnecessarily.

```text
forgeflow/
├── README.md
├── pyproject.toml
├── docs/
│   ├── architecture.md
│   └── decisions/
├── src/
│   └── forgeflow/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── runtime/
│       │   ├── __init__.py
│       │   └── claude_code.py
│       └── models/
│           ├── __init__.py
│           └── execution.py
└── tests/
    ├── unit/
    └── integration/
```

The layout is a starting suggestion, not a requirement to create empty modules prematurely.

### Definition of done for Milestone 1

- The adapter has a typed, documented interface.
- It invokes Claude Code through a verified supported mechanism.
- It records completion status and exit code.
- It handles launch errors, non-zero exits, timeouts, and cancellation as far as the interface allows.
- It avoids unbounded output capture and indefinite execution.
- Unit tests cover success and failure paths.
- Tests and lint checks have actually been run.
- README documentation explains setup, usage, assumptions, and limitations.
- No secrets or proprietary employer code are included.
- Unverified assumptions are clearly identified.

**Start with the investigation and Milestone 1. Do not scaffold every planned feature before proving the Claude Code integration works.**
