"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useProjectName } from "@/components/projects/project-shell";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardError,
  CardPending,
  Checkbox,
  Field,
  PageHeader,
  RelativeTime,
  Textarea,
} from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { useOpenItems, useRequirements, useResolveOpenItem } from "@/lib/api/hooks";
import type { OpenItem } from "@/lib/api/types";
import { scrollToFirstProblem } from "@/lib/forms";
import {
  IMPACT_LABEL,
  IMPACT_TONE,
  OPEN_ITEM_KIND_LABEL,
  OPEN_ITEM_STATUS_LABEL,
  OPEN_ITEM_STATUS_TONE,
  plural,
} from "@/lib/labels";

const schema = z.object({
  resolution: z.string().trim().min(3, "Write the answer, or why the question doesn’t apply."),
});
type Values = z.infer<typeof schema>;

function ResolveForm({ name, item }: { name: string; item: OpenItem }) {
  const [open, setOpen] = useState(false);
  const resolve = useResolveOpenItem(name);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), mode: "onBlur", defaultValues: { resolution: "" } });
  const pendingDismiss = resolve.isPending ? resolve.variables?.dismiss : undefined;
  const submit = (dismiss: boolean) =>
    handleSubmit((v) => resolve.mutate({ key: item.key, resolution: v.resolution, dismiss }), scrollToFirstProblem);
  const id = `answer-${item.key}`;

  if (!open)
    return (
      <div className="mt-4">
        <Button variant="secondary" onClick={() => setOpen(true)} aria-controls={id}>
          {item.kind === "assumption" ? "Confirm or correct" : "Answer this"}
        </Button>
      </div>
    );

  return (
    <form noValidate onSubmit={submit(false)} className="mt-4">
      <fieldset disabled={resolve.isPending}>
        <Field
          label={item.kind === "assumption" ? "Confirm or correct the assumption" : "Your answer"}
          error={errors.resolution?.message}
          hint="Then update the related requirements so the answer is reflected in their criteria."
        >
          <Textarea
            id={id}
            {...register("resolution")}
            rows={2}
            autoFocus
            aria-invalid={!!errors.resolution}
          />
        </Field>
      </fieldset>
      {resolve.isError && (
        <div className="mt-4">
          <Alert tone="error">{errorMessage(resolve.error)}</Alert>
        </div>
      )}
      <div className="mt-4 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={resolve.isPending}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="secondary"
          loading={pendingDismiss === true}
          disabled={resolve.isPending}
          onClick={submit(true)}
        >
          Dismiss as not applicable
        </Button>
        <Button type="submit" loading={pendingDismiss === false} disabled={resolve.isPending}>
          Save answer
        </Button>
      </div>
    </form>
  );
}

function QuestionCard({
  name,
  item,
  keysById,
}: {
  name: string;
  item: OpenItem;
  keysById: Map<string, string>;
}) {
  const base = `/projects/${encodeURIComponent(name)}`;
  return (
    <Card as="article" className="p-5 md:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold tabular-nums text-muted">{item.key}</span>
        <Badge tone={OPEN_ITEM_STATUS_TONE[item.status]}>{OPEN_ITEM_STATUS_LABEL[item.status]}</Badge>
        <Badge tone={IMPACT_TONE[item.impact]}>{IMPACT_LABEL[item.impact]}</Badge>
        <span className="text-xs font-medium text-muted">{OPEN_ITEM_KIND_LABEL[item.kind]}</span>
      </div>
      <h2 className="mt-3 text-base font-semibold leading-snug text-ink">{item.description}</h2>

      {item.source?.quote && (
        <p className="mt-3 border-l-2 border-line pl-3 text-sm text-muted">
          “{item.source.quote}” <span className="text-xs">brief v{item.source.brief_version}</span>
        </p>
      )}

      {item.related_requirement_ids.length > 0 && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
          Affects
          {item.related_requirement_ids.map((id) => {
            const key = keysById.get(id);
            return key ? (
              <Link
                key={id}
                href={`${base}/requirements/${key}`}
                className="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-brand hover:bg-brand/15"
              >
                {key}
              </Link>
            ) : null;
          })}
        </p>
      )}

      {item.status === "open" ? (
        <ResolveForm name={name} item={item} />
      ) : (
        <div className="mt-4 rounded-lg bg-brand/5 px-4 py-3 text-sm">
          <p className="text-ink">{item.resolution}</p>
          <p className="mt-1 text-xs text-muted">
            {item.status === "dismissed" ? "Dismissed" : "Answered"} by {item.resolved_by}
            {item.resolved_at && (
              <>
                {" · "}
                <RelativeTime iso={item.resolved_at} />
              </>
            )}
          </p>
        </div>
      )}
    </Card>
  );
}

export default function QuestionsPage() {
  const name = useProjectName();
  const [showClosed, setShowClosed] = useState(false);
  const items = useOpenItems(name, showClosed);
  const requirements = useRequirements(name);
  const keysById = new Map((requirements.data ?? []).map((r) => [r.id, r.key]));
  const openCount = items.data?.filter((i) => i.status === "open").length ?? 0;
  const highImpact = items.data?.filter((i) => i.status === "open" && i.impact === "high").length ?? 0;

  // Highest impact first, so the answers that most change the plan come first.
  const order = { high: 0, medium: 1, low: 2 } as const;
  const sorted = [...(items.data ?? [])].sort(
    (a, b) =>
      Number(a.status !== "open") - Number(b.status !== "open") ||
      order[a.impact] - order[b.impact] ||
      a.key.localeCompare(b.key),
  );

  return (
    <>
      <PageHeader
        eyebrow="Step 3"
        title="Open questions"
        description="Gaps, ambiguities and assumptions the analyst found instead of guessing. Answer the high-impact ones before planning starts."
      />

      <div className="max-w-xs">
        <Checkbox
          label="Show answered and dismissed"
          checked={showClosed}
          onChange={(e) => setShowClosed(e.target.checked)}
        />
      </div>

      {items.isPending && <CardPending message="Loading questions…" />}
      {items.isError && <CardError message={errorMessage(items.error)} onRetry={() => items.refetch()} />}

      {items.isSuccess && openCount > 0 && (
        <p className="text-sm text-muted" role="status">
          {plural(openCount, "question")} waiting on you
          {highImpact > 0 && `, ${highImpact} of them high impact`}.
        </p>
      )}

      {items.isSuccess && openCount === 0 && (
        <Card className="text-center">
          <div className="brand-gradient mx-auto flex h-16 w-16 items-center justify-center rounded-full text-white">
            <svg viewBox="0 0 24 24" className="h-8 w-8 fill-none stroke-current stroke-2" aria-hidden>
              <path d="M5 13l5 5L19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h2 className="mt-6 text-2xl font-extrabold text-ink">No open questions</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted">
            {showClosed || (requirements.data?.length ?? 0) > 0
              ? "Everything the analyst raised has an answer. Make sure the requirements reflect them."
              : "Questions appear here after the brief is analysed."}
          </p>
        </Card>
      )}

      {sorted.map((item) => (
        <QuestionCard key={item.id} name={name} item={item} keysById={keysById} />
      ))}
    </>
  );
}
