"use client";

import type { Control, FieldValues, UseFormRegister } from "react-hook-form";
import { useFieldArray } from "react-hook-form";

import { PlusIcon } from "@/components/ui/icons";
import { Button, Input } from "@/components/ui/primitives";

type WithCriteria = FieldValues & { acceptance_criteria: { text: string }[] };

/** Editable list of acceptance criteria. Empty rows are dropped on save. */
export function CriteriaEditor<T extends WithCriteria>({
  control,
  register,
}: {
  control: Control<T>;
  register: UseFormRegister<T>;
}) {
  // react-hook-form's generic paths can't see through the WithCriteria constraint.
  const { fields, append, remove } = useFieldArray({
    control: control as unknown as Control<WithCriteria>,
    name: "acceptance_criteria",
  });
  const reg = register as unknown as UseFormRegister<WithCriteria>;

  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium text-ink">Acceptance criteria</legend>
      <p className="mb-3 text-[13px] leading-snug text-muted">
        Each one should pass or fail when tested, e.g. “Orders after 11:00 are rejected with a message”.
      </p>
      {fields.length === 0 && (
        <p className="mb-3 rounded-lg border border-dashed border-ink/20 px-4 py-3 text-sm text-muted">
          No criteria yet. Without them this requirement can’t be verified.
        </p>
      )}
      <ol className="space-y-2">
        {fields.map((field, i) => (
          <li key={field.id} className="flex items-center gap-2">
            <span className="w-11 shrink-0 text-xs font-semibold tabular-nums text-muted">AC-{i + 1}</span>
            <Input
              {...reg(`acceptance_criteria.${i}.text` as const)}
              aria-label={`Acceptance criterion ${i + 1}`}
            />
            <button
              type="button"
              onClick={() => remove(i)}
              aria-label={`Remove acceptance criterion ${i + 1}`}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-line text-muted transition-colors hover:text-ink"
            >
              ✕
            </button>
          </li>
        ))}
      </ol>
      <Button
        type="button"
        variant="secondary"
        className="mt-3"
        onClick={() => append({ text: "" })}
      >
        <PlusIcon /> Add a criterion
      </Button>
    </fieldset>
  );
}
