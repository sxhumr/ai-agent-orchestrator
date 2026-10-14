"""Human-readable export of a project's requirements and open items."""

from __future__ import annotations

import json
from pathlib import Path

from forgeflow.models.requirements import Brief, OpenItem, Project, Requirement


def render_markdown(
    project: Project, brief: Brief | None, requirements: list[Requirement], items: list[OpenItem]
) -> str:
    keys_by_id = {r.id: r.key for r in requirements}
    lines = [f"# {project.name}: requirements", ""]
    if project.description:
        lines += [project.description, ""]
    lines += [f"- Status: `{project.status.value}`"]
    if brief is not None:
        source = f" ({brief.source_name})" if brief.source_name else ""
        lines += [f"- Brief: v{brief.version}{source}"]
    lines += [f"- Requirements: {len(requirements)}", f"- Open items: {len(items)}", ""]

    lines += ["## Requirements", ""]
    for r in requirements:
        lines += [
            f"### {r.key} — {r.title}",
            "",
            f"`{r.requirement_type.value}` · priority `{r.priority.value}` · "
            f"status `{r.status.value}` · confidence `{r.confidence.value}` · v{r.version}",
            "",
            r.description,
            "",
        ]
        if r.source and r.source.quote:
            marker = "" if r.source.quote_found else " _(not found verbatim in brief)_"
            lines += [
                f"> {r.source.quote}",
                ">",
                f"> — brief v{r.source.brief_version}{marker}",
                "",
            ]
        elif r.origin.value == "analyst":
            lines += ["_No source quote: inferred by the analyst._", ""]
        if r.acceptance_criteria:
            lines += ["**Acceptance criteria**", ""]
            lines += [f"- **{c.key}** {c.description}" for c in r.acceptance_criteria]
            lines += [""]

    lines += ["## Open items", ""]
    if not items:
        lines += ["None.", ""]
    for item in items:
        related = ", ".join(keys_by_id.get(i, i) for i in item.related_requirement_ids)
        lines += [
            f"### {item.key} — {item.kind.value.replace('_', ' ')} "
            f"(impact {item.impact.value}, {item.status.value})",
            "",
            item.description,
            "",
        ]
        if related:
            lines += [f"Related: {related}", ""]
        if item.resolution:
            lines += [f"**Resolution** ({item.resolved_by}): {item.resolution}", ""]
    return "\n".join(lines).rstrip() + "\n"


def export_requirements(
    out_dir: Path,
    project: Project,
    brief: Brief | None,
    requirements: list[Requirement],
    items: list[OpenItem],
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "requirements.md"
    md.write_text(render_markdown(project, brief, requirements, items))
    data = {
        "project": project.model_dump(mode="json"),
        "brief": brief.model_dump(mode="json") if brief else None,
        "requirements": [r.model_dump(mode="json") for r in requirements],
        "open_items": [i.model_dump(mode="json") for i in items],
    }
    js = out_dir / "requirements.json"
    js.write_text(json.dumps(data, indent=2) + "\n")
    return [md, js]
