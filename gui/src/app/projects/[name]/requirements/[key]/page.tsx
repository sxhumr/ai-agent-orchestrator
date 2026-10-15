"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { CriteriaEditor } from "@/components/projects/criteria-editor";
import { useProjectName } from "@/components/projects/project-shell";
import {
  confidenceOptions,
  criteriaToStrings,
  priorityOptions,
  requirementTextFields,
  statusOptions,
  typeOptions,
} from "@/components/projects/requirement-form-fields";
import { SourceFlag } from "@/components/projects/source-flag";
import { ArrowLeftIcon } from "@/components/ui/icons";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardError,
  CardPending,
  Field,
  Input,
  RelativeTime,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { useRequirement, useUpdateRequirement } from "@/lib/api/hooks";
import type { Requirement, RequirementChanges, RequirementDetail } from "@/lib/api/types";
import { scrollToFirstProblem } from "@/lib/forms";
import {
  CONFIDENCE_LABEL,
  IMPACT_LABEL,
  NEUTRAL_TONE,
  OPEN_ITEM_KIND_LABEL,
  OPEN_ITEM_STATUS_LABEL,
  OPEN_ITEM_STATUS_TONE,
  PRIORITY_LABEL,
  REQUIREMENT_STATUS_LABEL,
  REQUIREMENT_STATUS_TONE,
  REQUIREMENT_TYPE_LABEL,
} from "@/lib/labels";

const editSchema = z.object({
  ...requirementTextFields,
  status: z.enum(["proposed", "accepted", "rejected", "removed"]),
  confidence: z.enum(["high", "medium", "low"]),
  change_note: z.string().trim().max(500, "Keep the note under 500 characters."),
});
type EditValues = z.infer<typeof editSchema>;

function toValues(r: Requirement): EditValues {
  return {
    title: r.title,
    description: r.description,
    requirement_type: r.requirement_type,
    priority: r.priority,
    status: r.status,
    confidence: r.confidence,
    acceptance_criteria: r.acceptance_criteria.map((c) => ({ text: c.description })),
    change_note: "",
  };
}

/** Only send what changed, so the version history records real edits. */
function diff(r: Requirement, v: EditValues): RequirementChanges {
  const changes: RequirementChanges = {};
  if (v.title !== r.title) changes.title = v.title;
  if (v.description !== r.description) changes.description = v.description;
  if (v.requirement_type !== r.requirement_type) changes.requirement_type = v.requirement_type;
  if (v.priority !== r.priority) changes.priority = v.priority;
  if (v.status !== r.status) changes.status = v.status;
  if (v.confidence !== r.confidence) changes.confidence = v.confidence;
  const criteria = criteriaToStrings(v.acceptance_criteria);
  const current = r.acceptance_criteria.map((c) => c.description);
  if (criteria.join("\n") !== current.join("\n")) changes.acceptance_criteria = criteria;
  return changes;
}

function EditForm({ name, requirement }: { name: string; requirement: Requirement }) {
  const update = useUpdateRequirement(name, requirement.key);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    mode: "onBlur",
    defaultValues: toValues(requirement),
  });

  const onSubmit = handleSubmit((v) => {
    const changes = diff(requirement, v);
    if (Object.keys(changes).length === 0) {
      setError("root", { message: "Nothing has changed yet, so there’s no new version to save." });
      return;
    }
    update.mutate({ ...changes, change_note: v.change_note || null });
  }, scrollToFirstProblem);

  return (
    <form noValidate onSubmit={onSubmit}>
      <fieldset disabled={update.isPending} className="mt-6 space-y-5">
        <Field label="Title" required error={errors.title?.message}>
          <Input {...register("title")} aria-invalid={!!errors.title} />
        </Field>
        <Field label="Description" required error={errors.description?.message}>
          <Textarea {...register("description")} rows={3} aria-invalid={!!errors.description} />
        </Field>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Status" hint="Accepted requirements become the baseline for planning.">
            <Select {...register("status")}>{statusOptions()}</Select>
          </Field>
          <Field label="Priority">
            <Select {...register("priority")}>{priorityOptions()}</Select>
          </Field>
          <Field label="Type">
            <Select {...register("requirement_type")}>{typeOptions()}</Select>
          </Field>
          <Field label="Confidence" hint="How sure you are this reflects what the client wants.">
            <Select {...register("confidence")}>{confidenceOptions()}</Select>
          </Field>
        </div>
        <CriteriaEditor control={control} register={register} />
        <Field
          label="Why this changed"
          error={errors.change_note?.message}
          hint="Optional, but it’s what you’ll see in the history, e.g. “Q-004 answered”."
        >
          <Input {...register("change_note")} aria-invalid={!!errors.change_note} />
        </Field>
      </fieldset>

      {(errors.root || update.isError) && (
        <div className="mt-5">
          <Alert tone="error">{errors.root?.message ?? errorMessage(update.error)}</Alert>
        </div>
      )}

      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-ink/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[13px] text-muted">
          {isDirty
            ? `Saving creates version ${requirement.version + 1}. Version ${requirement.version} stays in the history.`
            : "Change a field to save a new version."}
        </p>
        <Button type="submit" loading={update.isPending}>
          Save version {requirement.version + 1}
        </Button>
      </div>
    </form>
  );
}

function QuickDecision({ name, requirement }: { name: string; requirement: Requirement }) {
  const update = useUpdateRequirement(name, requirement.key);
  const pending = update.isPending ? update.variables?.status : undefined;
  if (requirement.status !== "proposed") return null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button
          loading={pending === "accepted"}
          disabled={update.isPending}
          onClick={() => update.mutate({ status: "accepted", change_note: "Accepted" })}
        >
          Accept requirement
        </Button>
        <Button
          variant="secondary"
          loading={pending === "rejected"}
          disabled={update.isPending}
          onClick={() => update.mutate({ status: "rejected", change_note: "Rejected" })}
        >
          Reject
        </Button>
      </div>
      {update.isError && <Alert tone="error">{errorMessage(update.error)}</Alert>}
    </div>
  );
}

function SidePanels({ name, detail }: { name: string; detail: RequirementDetail }) {
  const r = detail.requirement;
  const base = `/projects/${encodeURIComponent(name)}`;
  return (
    <div className="space-y-6">
      <Card className="p-5">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Source</h2>
        {r.source?.quote ? (
          <figure className="mt-3 rounded-lg border border-line bg-surface-2 p-4">
            <blockquote className="border-l-2 border-brand/40 pl-3 text-sm leading-relaxed text-ink">
              “{r.source.quote}”
            </blockquote>
            <figcaption className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
              <Link href={`${base}/brief`} className="font-semibold text-brand hover:underline">
                Brief v{r.source.brief_version}
              </Link>
              <SourceFlag r={r} />
            </figcaption>
          </figure>
        ) : (
          <p className="mt-3 text-sm text-muted">
            {r.origin === "developer"
              ? "Added by you, not taken from the brief."
              : `Inferred by the analyst from brief v${r.source?.brief_version ?? "?"} rather than quoted. Check it against the brief.`}
          </p>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Related questions</h2>
        {detail.open_items.length === 0 ? (
          <p className="mt-3 text-sm text-muted">None.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line rounded-lg border border-line">
            {detail.open_items.map((item) => (
              <li key={item.id} className="space-y-1.5 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold tabular-nums text-muted">{item.key}</span>
                  <Badge tone={OPEN_ITEM_STATUS_TONE[item.status]}>{OPEN_ITEM_STATUS_LABEL[item.status]}</Badge>
                </div>
                <p className="text-sm text-ink">{item.description}</p>
                <p className="text-xs text-muted">
                  {OPEN_ITEM_KIND_LABEL[item.kind]} · {IMPACT_LABEL[item.impact]}
                </p>
                {item.resolution && <p className="text-sm text-muted">Answer: {item.resolution}</p>}
              </li>
            ))}
          </ul>
        )}
        {detail.open_items.some((i) => i.status === "open") && (
          <Link href={`${base}/questions`} className="mt-3 inline-block text-sm font-semibold text-brand hover:underline">
            Answer on the questions page
          </Link>
        )}
      </Card>

      <Card className="p-5">
        <h2 className="text-sm font-bold uppercase tracking-wide text-muted">History</h2>
        <ol className="mt-3 divide-y divide-line rounded-lg border border-line">
          {[...detail.history].reverse().map((v) => (
            <li key={v.version} className="px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold tabular-nums text-ink">v{v.version}</span>
                <span className="text-xs text-muted">
                  <RelativeTime iso={v.updated_at} />
                </span>
              </div>
              <p className="mt-0.5 text-xs text-muted">
                {v.generated_by_run_id ? "Generated by the analyst" : "Edited by you"} ·{" "}
                {REQUIREMENT_STATUS_LABEL[v.status]}
              </p>
              {v.change_note && <p className="mt-1 text-sm text-ink">{v.change_note}</p>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

export default function RequirementPage() {
  const name = useProjectName();
  const key = decodeURIComponent(useParams<{ key: string }>().key);
  const detail = useRequirement(name, key);
  const base = `/projects/${encodeURIComponent(name)}`;

  const back = (
    <Link href={`${base}/requirements`} className="inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
      <ArrowLeftIcon /> All requirements
    </Link>
  );

  if (detail.isPending) return <CardPending message={`Loading ${key}…`} />;
  if (detail.isError) {
    if (detail.error instanceof ApiError && detail.error.status === 404)
      return (
        <Card>
          {back}
          <h1 className="mt-4 text-2xl font-extrabold text-ink">There’s no {key} in this project</h1>
          <p className="mt-1 text-sm text-muted">Pick one from the requirements list.</p>
        </Card>
      );
    return <CardError message={errorMessage(detail.error)} onRetry={() => detail.refetch()} />;
  }

  const r = detail.data.requirement;
  return (
    <>
      <div className="space-y-4">
        {back}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">
            <span className="tabular-nums">{r.key}</span> · version {r.version}
          </p>
          <h1 className="mt-1 text-2xl font-extrabold text-ink">{r.title}</h1>
          <p className="mt-1 text-sm text-muted">{r.description}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone={REQUIREMENT_STATUS_TONE[r.status]}>{REQUIREMENT_STATUS_LABEL[r.status]}</Badge>
            <Badge tone={NEUTRAL_TONE}>{PRIORITY_LABEL[r.priority]}</Badge>
            <Badge tone={NEUTRAL_TONE}>{REQUIREMENT_TYPE_LABEL[r.requirement_type]}</Badge>
            <Badge tone={NEUTRAL_TONE}>{CONFIDENCE_LABEL[r.confidence]}</Badge>
          </div>
        </div>
        <QuickDecision name={name} requirement={r} />
      </div>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <Card className="min-w-0 flex-1 p-5 md:p-6">
          <h2 className="text-xl font-extrabold text-ink">Edit</h2>
          <p className="mt-1 text-sm text-muted">Every save is a new version; nothing is overwritten.</p>
          {/* Remount on a new version so the form starts from the saved values. */}
          <EditForm key={r.version} name={name} requirement={r} />
        </Card>
        <div className="w-full shrink-0 lg:w-80">
          <SidePanels name={name} detail={detail.data} />
        </div>
      </div>
    </>
  );
}
