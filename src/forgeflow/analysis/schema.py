"""The structured output the requirements analyst must return.

This schema is sent to Claude Code via ``--json-schema`` and the result is
re-validated here, so the model never writes persisted records directly: ForgeFlow
assigns ids and keys, resolves references and checks source quotes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from forgeflow.models.requirements import (
    Confidence,
    Impact,
    OpenItemKind,
    Priority,
    RequirementType,
)


class DraftRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(
        min_length=1,
        max_length=20,
        description="Local reference such as R1, unique within this response.",
    )
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    requirement_type: RequirementType
    priority: Priority
    confidence: Confidence = Field(
        description="high when stated explicitly in the brief; low when inferred."
    )
    source_quote: str | None = Field(
        description=(
            "A short verbatim excerpt from the brief that supports this requirement, "
            "or null if it is inferred rather than stated."
        )
    )
    acceptance_criteria: list[str] = Field(
        description="Objectively testable conditions; each one checkable as pass/fail."
    )


class DraftOpenItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: OpenItemKind
    description: str = Field(
        min_length=1,
        description="For questions, phrase as a direct question to the developer.",
    )
    related_refs: list[str] = Field(description="refs of the requirements this affects.")
    impact: Impact
    source_quote: str | None = Field(description="Verbatim excerpt from the brief, or null.")


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, description="Two or three sentences on the brief.")
    requirements: list[DraftRequirement] = Field(min_length=1)
    open_items: list[DraftOpenItem]

    @model_validator(mode="after")
    def _check_refs(self) -> AnalysisOutput:
        refs = [r.ref for r in self.requirements]
        duplicates = sorted({r for r in refs if refs.count(r) > 1})
        if duplicates:
            raise ValueError(f"duplicate requirement refs: {', '.join(duplicates)}")
        known = set(refs)
        for i, item in enumerate(self.open_items):
            dangling = [r for r in item.related_refs if r not in known]
            if dangling:
                raise ValueError(f"open_items[{i}] references unknown refs: {', '.join(dangling)}")
        return self
