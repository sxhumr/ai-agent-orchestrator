"use client";

import { z } from "zod";

import { CONFIDENCE_LABEL, PRIORITY_LABEL, REQUIREMENT_STATUS_LABEL, REQUIREMENT_TYPE_LABEL } from "@/lib/labels";

const options = <T extends string>(labels: Record<T, string>) =>
  (Object.entries(labels) as [T, string][]).map(([value, label]) => (
    <option key={value} value={value}>
      {label}
    </option>
  ));

export const typeOptions = () => options(REQUIREMENT_TYPE_LABEL);
export const priorityOptions = () => options(PRIORITY_LABEL);
export const statusOptions = () => options(REQUIREMENT_STATUS_LABEL);
export const confidenceOptions = () => options(CONFIDENCE_LABEL);

export const criterionSchema = z.object({ text: z.string() });

export const requirementTextFields = {
  title: z
    .string()
    .trim()
    .min(1, "Give the requirement a short title.")
    .max(200, "Keep the title under 200 characters."),
  description: z.string().trim().min(1, "Describe what the requirement means in a sentence or two."),
  requirement_type: z.enum(["functional", "non_functional", "constraint", "business_goal"]),
  priority: z.enum(["must", "should", "could", "wont"]),
  // Kept as objects so react-hook-form's field array can track each row.
  acceptance_criteria: z.array(criterionSchema),
};

export function criteriaToStrings(rows: { text: string }[]): string[] {
  return rows.map((r) => r.text.trim()).filter(Boolean);
}
