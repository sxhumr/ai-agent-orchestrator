"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { CriteriaEditor } from "@/components/projects/criteria-editor";
import { useProjectName } from "@/components/projects/project-shell";
import {
  criteriaToStrings,
  priorityOptions,
  requirementTextFields,
  typeOptions,
} from "@/components/projects/requirement-form-fields";
import { SourceFlag } from "@/components/projects/source-flag";
import { PlusIcon, TickIcon } from "@/components/ui/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardError,
  CardPending,
  cx,
  Field,
  Input,
  PageHeader,
  PageTitle,
  primaryLinkClass,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { useAddRequirement, useRequirements } from "@/lib/api/hooks";
import type { RequirementStatus } from "@/lib/api/types";
import { confirmDiscard, scrollToFirstProblem } from "@/lib/forms";
import {
  PRIORITY_LABEL,
  REQUIREMENT_STATUS_LABEL,
  REQUIREMENT_STATUS_TONE,
  REQUIREMENT_TYPE_LABEL,
} from "@/lib/labels";

const addSchema = z.object(requirementTextFields);
type AddValues = z.infer<typeof addSchema>;

function AddRequirementForm({ name, onDone }: { name: string; onDone: (key: string) => void }) {
  const add = useAddRequirement(name);
  const {
    register,
    control,
    handleSubmit,
    setFocus,
    formState: { errors, isDirty },
  } = useForm<AddValues>({
    resolver: zodResolver(addSchema),
    mode: "onBlur",
    defaultValues: {
      title: "",
      description: "",
      requirement_type: "functional",
      priority: "should",
      acceptance_criteria: [{ text: "" }],
    },
  });

  useEffect(() => setFocus("title"), [setFocus]);

  const cancel = () => {
    if (confirmDiscard(isDirty, "this requirement")) onDone("");
  };

  return (
    <form
      noValidate
      onKeyDown={(e) => e.key === "Escape" && cancel()}
      onSubmit={handleSubmit(
        (v) =>
          add.mutate(
            { ...v, acceptance_criteria: criteriaToStrings(v.acceptance_criteria) },
            { onSuccess: (r) => onDone(r.key) },
          ),
        scrollToFirstProblem,
      )}
    >
      <fieldset disabled={add.isPending} className="mt-6 space-y-5">
        <Field label="Title" required error={errors.title?.message}>
          <Input {...register("title")} aria-invalid={!!errors.title} />
        </Field>
        <Field label="Description" required error={errors.description?.message}>
          <Textarea {...register("description")} rows={3} aria-invalid={!!errors.description} />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Type">
            <Select {...register("requirement_type")}>{typeOptions()}</Select>
          </Field>
          <Field label="Priority">
            <Select {...register("priority")}>{priorityOptions()}</Select>
          </Field>
        </div>
        <CriteriaEditor control={control} register={register} />
      </fieldset>
      {add.isError && (
        <div className="mt-5">
          <Alert tone="error">{errorMessage(add.error)}</Alert>
        </div>
      )}
      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-ink/10 pt-5 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" onClick={cancel}>
          Cancel
        </Button>
        <Button type="submit" loading={add.isPending}>
          Add requirement
        </Button>
      </div>
    </form>
  );
}

type Filter = "all" | RequirementStatus | "unverified";

export default function RequirementsPage() {
  const name = useProjectName();
  const router = useRouter();
  const requirements = useRequirements(name);
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const addButton = useRef<HTMLButtonElement>(null);
  const wasAdding = useRef(false);
  const base = `/projects/${encodeURIComponent(name)}`;

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: 0, proposed: 0, accepted: 0, rejected: 0, removed: 0, unverified: 0 };
    for (const r of requirements.data ?? []) {
      c.all += 1;
      c[r.status] += 1;
      if (r.origin === "analyst" && !r.source?.quote_found) c.unverified += 1;
    }
    return c;
  }, [requirements.data]);

  const visible = (requirements.data ?? []).filter((r) =>
    filter === "all"
      ? true
      : filter === "unverified"
        ? r.origin === "analyst" && !r.source?.quote_found
        : r.status === filter,
  );

  // Removed only appears once something has been removed.
  const statuses: RequirementStatus[] = ["proposed", "accepted", "rejected", "removed"];
  const filters: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    ...statuses
      .filter((s) => s !== "removed" || counts.removed > 0)
      .map((s) => ({ id: s, label: REQUIREMENT_STATUS_LABEL[s] })),
    { id: "unverified", label: "Unverified source" },
  ];

  useEffect(() => {
    if (wasAdding.current && !adding) addButton.current?.focus();
    wasAdding.current = adding;
  }, [adding]);

  // Rows act as links, but leave text selection and new-tab clicks alone.
  const openRow = (e: React.MouseEvent, href: string) => {
    if (window.getSelection()?.toString()) return;
    if (e.metaKey || e.ctrlKey) window.open(href, "_blank");
    else router.push(href);
  };

  return (
    <>
      <PageTitle parts={[name, "Requirements"]} />
      <PageHeader
        eyebrow="Step 2"
        title="Requirements"
        description="Proposed by the analyst, decided by you. Open one to edit it, accept it or see its history."
        actions={
          !adding && (
            <Button ref={addButton} variant="secondary" onClick={() => setAdding(true)}>
              <PlusIcon /> Add requirement
            </Button>
          )
        }
      />

      {adding && (
        <Card>
          <h2 className="text-xl font-extrabold text-ink">New requirement</h2>
          <p className="mt-1 text-sm text-muted">For needs the brief doesn’t cover. It’s marked as added by you.</p>
          <AddRequirementForm
            name={name}
            onDone={(key) => {
              setAdding(false);
              if (key) router.push(`${base}/requirements/${key}`);
            }}
          />
        </Card>
      )}

      {requirements.isPending && <CardPending message="Loading requirements…" />}
      {requirements.isError && (
        <CardError message={errorMessage(requirements.error)} onRetry={() => requirements.refetch()} />
      )}

      {requirements.isSuccess && requirements.data.length === 0 && !adding && (
        <Card>
          <h2 className="text-xl font-extrabold text-ink">No requirements yet</h2>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Generate them from the brief, or add them by hand if you already know what’s needed.
          </p>
          <Link href={`${base}/brief`} className={`${primaryLinkClass} mt-6`}>
            Go to the brief
          </Link>
        </Card>
      )}

      {requirements.isSuccess && requirements.data.length > 0 && (
        <>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Filter requirements">
            {filters.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={filter === f.id}
                onClick={() => setFilter(f.id)}
                className={cx(
                  "inline-flex min-h-11 items-center gap-2 rounded-lg border px-3.5 text-sm font-semibold transition-colors",
                  filter === f.id
                    ? "border-brand/40 bg-brand/5 text-brand"
                    : "border-line bg-surface text-muted hover:text-ink",
                )}
              >
                {filter === f.id && <TickIcon />}
                {f.label}
                <span className="tabular-nums text-xs font-medium">{counts[f.id]}</span>
              </button>
            ))}
          </div>

          <div className="relative overflow-x-auto rounded-2xl border border-line bg-surface shadow-sm shadow-ink/[0.03]">
            <table className="w-full min-w-2xl text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-semibold">Requirement</th>
                  <th className="px-4 py-3 font-semibold">Priority</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Source</th>
                  <th className="px-4 py-3 text-right font-semibold">Criteria</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const href = `${base}/requirements/${r.key}`;
                  return (
                    <tr
                      key={r.id}
                      onClick={(e) => openRow(e, href)}
                      className="cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-brand/[0.03]"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={href}
                          onClick={(e) => e.stopPropagation()}
                          className="font-semibold text-ink hover:text-brand"
                        >
                          {r.title}
                        </Link>
                        <p className="text-xs text-muted">
                          {r.key} · {REQUIREMENT_TYPE_LABEL[r.requirement_type]}
                          {r.version > 1 && <span className="tabular-nums"> · v{r.version}</span>}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-ink">{PRIORITY_LABEL[r.priority]}</td>
                      <td className="px-4 py-3">
                        <Badge tone={REQUIREMENT_STATUS_TONE[r.status]}>{REQUIREMENT_STATUS_LABEL[r.status]}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <SourceFlag r={r} />
                      </td>
                      <td
                        className={cx(
                          "px-4 py-3 text-right tabular-nums",
                          r.acceptance_criteria.length ? "text-ink" : "text-muted",
                        )}
                      >
                        {r.acceptance_criteria.length || "None"}
                      </td>
                    </tr>
                  );
                })}
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted">
                      No requirements match this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
