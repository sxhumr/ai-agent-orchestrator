// Mirrors the Pydantic models served by `forgeflow serve` (src/forgeflow/api/app.py).

export type ProjectStatus =
  | "INITIALISING"
  | "DISCOVERY"
  | "AWAITING_CLARIFICATION"
  | "REQUIREMENTS_REVIEW";

export type RequirementType = "functional" | "non_functional" | "constraint" | "business_goal";
export type Priority = "must" | "should" | "could" | "wont";
export type Confidence = "high" | "medium" | "low";
export type RequirementStatus = "proposed" | "accepted" | "rejected" | "removed";
export type Origin = "analyst" | "developer";
export type OpenItemKind = "assumption" | "open_question" | "ambiguity" | "potential_conflict";
export type Impact = "high" | "medium" | "low";
export type OpenItemStatus = "open" | "resolved" | "dismissed";

export interface Project {
  id: string;
  name: string;
  root_path: string;
  description: string;
  status: ProjectStatus;
  configuration: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  project: Project;
  brief_version: number | null;
  requirement_count: number;
  requirements_by_status: Partial<Record<RequirementStatus, number>>;
  unverified_source_count: number;
  open_item_count: number;
  run_count: number;
  total_cost_usd: number;
  analysis_running: boolean;
}

export interface Brief {
  id: string;
  project_id: string;
  version: number;
  content: string;
  source_name: string | null;
  created_at: string;
}

export interface SourceReference {
  brief_id: string;
  brief_version: number;
  quote: string | null;
  quote_found: boolean;
}

export interface AcceptanceCriterion {
  key: string;
  description: string;
}

export interface Requirement {
  id: string;
  project_id: string;
  key: string;
  title: string;
  description: string;
  requirement_type: RequirementType;
  priority: Priority;
  source: SourceReference | null;
  acceptance_criteria: AcceptanceCriterion[];
  status: RequirementStatus;
  confidence: Confidence;
  origin: Origin;
  generated_by_run_id: string | null;
  version: number;
  change_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface OpenItem {
  id: string;
  project_id: string;
  key: string;
  kind: OpenItemKind;
  description: string;
  related_requirement_ids: string[];
  impact: Impact;
  status: OpenItemStatus;
  resolution: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  source: SourceReference | null;
  generated_by_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentRun {
  id: string;
  project_id: string;
  task_id: string | null;
  role: string;
  runtime: string;
  session_reference: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  exit_code: number | null;
  cost_usd: number | null;
  summary: string | null;
  error_details: string | null;
}

export interface RequirementDetail {
  requirement: Requirement;
  history: Requirement[];
  open_items: OpenItem[];
}

export interface AnalysisResult {
  summary: string;
  brief_version: number;
  run: AgentRun;
  requirement_keys: string[];
  open_item_keys: string[];
  unverified_sources: string[];
}

export interface RequirementChanges {
  title?: string;
  description?: string;
  requirement_type?: RequirementType;
  priority?: Priority;
  status?: RequirementStatus;
  confidence?: Confidence;
  acceptance_criteria?: string[];
  change_note?: string | null;
}
