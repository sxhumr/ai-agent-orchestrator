// One source of truth for status wording and badge tones. Never inline these at call sites.

import type {
  Confidence,
  Impact,
  OpenItemKind,
  OpenItemStatus,
  Priority,
  ProjectStatus,
  RequirementStatus,
  RequirementType,
} from "./api/types";

const NEUTRAL = "border-line bg-background text-muted";
const BRAND = "border-brand/20 bg-brand/[0.06] text-brand";
const SUCCESS =
  "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300";
const WARNING =
  "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300";
const ERROR =
  "border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300";

export const PROJECT_STATUS_LABEL: Record<ProjectStatus, string> = {
  INITIALISING: "Getting started",
  DISCOVERY: "Discovery",
  AWAITING_CLARIFICATION: "Needs answers",
  REQUIREMENTS_REVIEW: "Ready for review",
};

export const PROJECT_STATUS_TONE: Record<ProjectStatus, string> = {
  INITIALISING: NEUTRAL,
  DISCOVERY: BRAND,
  AWAITING_CLARIFICATION: WARNING,
  REQUIREMENTS_REVIEW: BRAND,
};

export const REQUIREMENT_STATUS_LABEL: Record<RequirementStatus, string> = {
  proposed: "Proposed",
  accepted: "Accepted",
  rejected: "Rejected",
  removed: "Removed",
};

export const REQUIREMENT_STATUS_TONE: Record<RequirementStatus, string> = {
  proposed: BRAND,
  accepted: SUCCESS,
  rejected: ERROR,
  removed: NEUTRAL,
};

export const REQUIREMENT_TYPE_LABEL: Record<RequirementType, string> = {
  functional: "Functional",
  non_functional: "Non-functional",
  constraint: "Constraint",
  business_goal: "Business goal",
};

export const PRIORITY_LABEL: Record<Priority, string> = {
  must: "Must",
  should: "Should",
  could: "Could",
  wont: "Won’t",
};

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export const OPEN_ITEM_KIND_LABEL: Record<OpenItemKind, string> = {
  open_question: "Open question",
  ambiguity: "Ambiguity",
  potential_conflict: "Potential conflict",
  assumption: "Assumption",
};

export const IMPACT_LABEL: Record<Impact, string> = {
  high: "High impact",
  medium: "Medium impact",
  low: "Low impact",
};

export const IMPACT_TONE: Record<Impact, string> = {
  high: WARNING,
  medium: BRAND,
  low: NEUTRAL,
};

export const OPEN_ITEM_STATUS_LABEL: Record<OpenItemStatus, string> = {
  open: "Open",
  resolved: "Resolved",
  dismissed: "Dismissed",
};

export const OPEN_ITEM_STATUS_TONE: Record<OpenItemStatus, string> = {
  open: WARNING,
  resolved: SUCCESS,
  dismissed: NEUTRAL,
};

export const RUN_STATUS_TONE: Record<string, string> = {
  succeeded: SUCCESS,
  failed: ERROR,
  timed_out: ERROR,
  cancelled: NEUTRAL,
  launch_error: ERROR,
  protocol_error: ERROR,
};

export const RUN_STATUS_LABEL: Record<string, string> = {
  succeeded: "Succeeded",
  failed: "Failed",
  timed_out: "Timed out",
  cancelled: "Cancelled",
  launch_error: "Couldn’t start",
  protocol_error: "Bad output",
};

export const NEUTRAL_TONE = NEUTRAL;
export const WARNING_TONE = WARNING;
export const SUCCESS_TONE = SUCCESS;

export function formatUsd(value: number | null | undefined): string {
  return `$${(value ?? 0).toFixed(2)}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
