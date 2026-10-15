"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Button, Card, Field, Input, Select, Spinner } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { useRequirements, useRunAnalysis } from "@/lib/api/hooks";
import type { ProjectSummary } from "@/lib/api/types";
import { scrollToFirstProblem } from "@/lib/forms";
import { plural } from "@/lib/labels";

const schema = z.object({
  max_budget_usd: z.coerce
    .number({ error: "Enter a budget in dollars, e.g. 1.00." })
    .min(0.1, "Allow at least $0.10, or the run will stop before it finishes.")
    .max(10, "Keep the budget at $10 or less for a single analysis."),
  model: z.string(),
});

type FormIn = z.input<typeof schema>;
type FormOut = z.output<typeof schema>;

function RunningCard({ version, polling }: { version: number | null; polling: boolean }) {
  return (
    <Card className="p-5 md:p-6">
      <div className="flex items-start gap-3">
        <Spinner className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <h2 className="text-xl font-extrabold text-ink">Analysing brief v{version}…</h2>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Claude Code is reading the brief with no access to your files. This usually takes
            30–60 seconds. You can leave this page; the results are saved when it finishes.
          </p>
          {/* Only true when this tab is polling for a run started elsewhere; while our
              own request is open, the response itself carries the result. */}
          {polling && (
            <p className="mt-3 flex items-center gap-2 text-xs font-medium text-muted">
              <span aria-hidden className="h-2 w-2 animate-pulse rounded-full bg-brand-cyan" />
              Live — checking every 3s
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

export function AnalysisPanel({ name, summary }: { name: string; summary: ProjectSummary }) {
  const run = useRunAnalysis(name);
  const requirements = useRequirements(name);
  const base = `/projects/${encodeURIComponent(name)}`;
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormIn, unknown, FormOut>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: { max_budget_usd: "1.00", model: "" },
  });

  if (summary.brief_version === null) return null;

  if (run.isPending || summary.analysis_running)
    return <RunningCard version={summary.brief_version} polling={!run.isPending} />;

  if (run.isSuccess) {
    const r = run.data;
    return (
      <Card className="space-y-4 p-5 md:p-6">
        <Alert tone="success" title="Analysis finished">
          {plural(r.requirement_keys.length, "requirement")} and {plural(r.open_item_keys.length, "open question")}{" "}
          from brief v{r.brief_version}, for ${(r.run.cost_usd ?? 0).toFixed(2)}.
          {r.unverified_sources.length > 0 &&
            ` ${plural(r.unverified_sources.length, "requirement")} couldn’t be matched to a quote in the brief: ${r.unverified_sources.join(", ")}.`}
        </Alert>
        <p className="text-sm text-muted">{r.summary}</p>
        <div className="flex flex-col gap-3 sm:flex-row">
          {r.open_item_keys.length > 0 && (
            <Link
              href={`${base}/questions`}
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-brand px-5 text-sm font-semibold text-white shadow-sm shadow-brand/25 transition-all hover:bg-brand-deep active:scale-[0.98]"
            >
              Answer the questions
            </Link>
          )}
          <Link
            href={`${base}/requirements`}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-line bg-surface px-5 text-sm font-semibold text-ink transition-all hover:border-brand/40 hover:text-brand active:scale-[0.98]"
          >
            Review requirements
          </Link>
        </div>
      </Card>
    );
  }

  if (summary.requirement_count > 0) {
    const sourceVersions = (requirements.data ?? [])
      .map((r) => r.source?.brief_version)
      .filter((v): v is number => typeof v === "number");
    const analysedVersion = sourceVersions.length ? Math.max(...sourceVersions) : null;
    const stale = analysedVersion !== null && analysedVersion < summary.brief_version;
    return (
      <Card className="space-y-4 p-5 md:p-6">
        <h2 className="text-xl font-extrabold text-ink">Analysis</h2>
        {stale ? (
          <Alert tone="warning" title={`Brief v${summary.brief_version} hasn’t been analysed`}>
            Your requirements came from brief v{analysedVersion}. Re-analysing a changed brief
            without losing your edits arrives with change-impact support. Until then, update the
            affected requirements by hand.
          </Alert>
        ) : (
          <Alert tone="info">
            Requirements were generated from brief v{analysedVersion ?? summary.brief_version}. Edit
            them directly; running the analysis again would duplicate them.
          </Alert>
        )}
      </Card>
    );
  }

  return (
    <Card className="p-5 md:p-6">
      <h2 className="text-xl font-extrabold text-ink">Generate requirements</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted">
        Claude Code reads brief v{summary.brief_version} and proposes requirements, testable acceptance
        criteria and the questions it needs answered. It runs with no tools and can’t see or change your
        files. Nothing is final until you accept it.
      </p>
      <form
        noValidate
        onSubmit={handleSubmit(
          (values) => run.mutate({ max_budget_usd: values.max_budget_usd, model: values.model || null }),
          scrollToFirstProblem,
        )}
      >
        <fieldset className="mt-6 grid gap-5 sm:grid-cols-2">
          <Field
            label="Budget limit"
            required
            error={errors.max_budget_usd?.message}
            hint="In US dollars. The run stops if it would spend more. A typical brief costs $0.10–$0.30."
          >
            <Input
              {...register("max_budget_usd")}
              inputMode="decimal"
              placeholder="1.00"
              aria-invalid={!!errors.max_budget_usd}
            />
          </Field>
          <Field label="Model" hint="Defaults to the model your Claude Code is set up with.">
            <Select {...register("model")}>
              <option value="">Claude Code default</option>
              <option value="fable">Fable</option>
              <option value="opus">Opus</option>
              <option value="sonnet">Sonnet</option>
            </Select>
          </Field>
        </fieldset>
        {run.isError && (
          <div className="mt-5">
            <Alert tone="error" title="The analysis didn’t produce usable requirements">
              {errorMessage(run.error)} The attempt is recorded under agent runs on the overview.
            </Alert>
          </div>
        )}
        <div className="mt-8 flex flex-col-reverse gap-3 border-t border-ink/10 pt-5 sm:flex-row sm:justify-end">
          <Button type="submit">{run.isError ? "Try the analysis again" : "Generate requirements"}</Button>
        </div>
      </form>
    </Card>
  );
}
