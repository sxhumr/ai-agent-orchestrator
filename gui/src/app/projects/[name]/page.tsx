"use client";

import Link from "next/link";

import { useProjectName } from "@/components/projects/project-shell";
import {
  Badge,
  Card,
  CardError,
  CardPending,
  InlinePending,
  PageHeader,
  RelativeTime,
  StatTile,
} from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { useProject, useRuns } from "@/lib/api/hooks";
import type { ProjectSummary } from "@/lib/api/types";
import { formatUsd, plural, RUN_STATUS_LABEL, RUN_STATUS_TONE } from "@/lib/labels";

function nextStep(s: ProjectSummary, base: string): { title: string; body: string; href: string; cta: string } {
  if (s.brief_version === null)
    return {
      title: "Add the business brief",
      body: "Paste what the client wants in their own words. Everything else is traced back to it.",
      href: `${base}/brief`,
      cta: "Add the brief",
    };
  if (s.requirement_count === 0)
    return {
      title: "Generate requirements",
      body: "Claude Code reads the brief and proposes requirements, acceptance criteria and questions. It takes about a minute.",
      href: `${base}/brief`,
      cta: "Go to analysis",
    };
  if (s.open_item_count > 0)
    return {
      title: `Answer ${plural(s.open_item_count, "open question")}`,
      body: "The analyst found gaps it shouldn’t guess about. Your answers decide what gets built.",
      href: `${base}/questions`,
      cta: "Answer questions",
    };
  const accepted = s.requirements_by_status.accepted ?? 0;
  const undecided = s.requirement_count - accepted - (s.requirements_by_status.rejected ?? 0) - (s.requirements_by_status.removed ?? 0);
  if (undecided > 0)
    return {
      title: `Review ${plural(undecided, "proposed requirement")}`,
      body: "Accept, reword or reject each one. Accepted requirements become the baseline for planning.",
      href: `${base}/requirements`,
      cta: "Review requirements",
    };
  return {
    title: "The requirements baseline is ready",
    body: "Every requirement has a decision. Architecture planning and approval arrive with the next milestone.",
    href: `${base}/requirements`,
    cta: "View requirements",
  };
}

function AcceptedProgress({ accepted, total }: { accepted: number; total: number }) {
  const pct = total ? Math.round((accepted / total) * 100) : 0;
  // 5% floor so the first accepted requirement is visible on a long list.
  const scale = accepted ? Math.max(pct, 5) / 100 : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-ink">Requirements accepted</span>
        <span className="tabular-nums text-muted">
          {accepted} / {total} · {pct}%
        </span>
      </div>
      <div className="relative mt-2 h-2 overflow-hidden rounded-full bg-ink/10" aria-hidden>
        <div
          className="brand-gradient absolute inset-0 origin-left overflow-hidden rounded-full transition-transform duration-700 ease-out"
          style={{ transform: `scaleX(${scale})` }}
        >
          <div className="progress-shimmer h-full w-full" />
        </div>
      </div>
    </div>
  );
}

function Runs({ name }: { name: string }) {
  const runs = useRuns(name);
  if (runs.isPending) return <InlinePending message="Loading agent runs…" />;
  if (runs.isError) return <p className="py-4 text-sm text-muted">{errorMessage(runs.error)}</p>;
  if (runs.data.length === 0)
    return <p className="py-4 text-sm text-muted">No agent has run for this project yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-xl text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
            <th className="px-4 py-3 font-semibold">Run</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Started</th>
            <th className="px-4 py-3 text-right font-semibold">Cost</th>
          </tr>
        </thead>
        <tbody>
          {[...runs.data].reverse().map((run) => (
            <tr key={run.id} className="border-b border-line/60 last:border-0">
              <td className="px-4 py-3">
                <p className="font-semibold text-ink">Requirements analyst</p>
                <p className="max-w-md truncate text-xs text-muted" title={run.summary ?? undefined}>
                  {run.error_details ?? run.summary ?? run.id}
                </p>
              </td>
              <td className="px-4 py-3">
                <Badge tone={RUN_STATUS_TONE[run.status] ?? RUN_STATUS_TONE.cancelled}>
                  {RUN_STATUS_LABEL[run.status] ?? run.status}
                </Badge>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-muted">
                <RelativeTime iso={run.started_at} />
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-ink">{formatUsd(run.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function OverviewPage() {
  const name = useProjectName();
  const project = useProject(name);
  const base = `/projects/${encodeURIComponent(name)}`;

  if (project.isPending) return <CardPending message="Loading the overview…" />;
  if (project.isError)
    return <CardError message={errorMessage(project.error)} onRetry={() => project.refetch()} />;

  const s = project.data;
  const step = nextStep(s, base);
  const accepted = s.requirements_by_status.accepted ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title={s.project.name}
        description={s.project.description || "No description yet."}
      />

      <div className="rounded-2xl border border-brand/15 bg-brand/[0.04] p-5 dark:bg-brand/10 md:p-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Next step</p>
        <h2 className="mt-1 text-xl font-extrabold text-ink">{step.title}</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">{step.body}</p>
        <Link
          href={step.href}
          className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl bg-brand px-5 text-sm font-semibold text-white shadow-sm shadow-brand/25 transition-all hover:bg-brand-deep active:scale-[0.98]"
        >
          {step.cta}
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Requirements" value={s.requirement_count} />
        <StatTile label="Accepted" value={accepted} />
        <StatTile
          label="Open questions"
          value={s.open_item_count}
          hint={s.open_item_count ? "Waiting on you" : undefined}
        />
        <StatTile label="Analyst spend" value={formatUsd(s.total_cost_usd)} hint={plural(s.run_count, "run")} />
      </div>

      {s.requirement_count > 0 && (
        <Card className="space-y-4 p-5 md:p-6">
          <AcceptedProgress accepted={accepted} total={s.requirement_count} />
          {s.unverified_source_count > 0 && (
            <p className="text-sm text-muted">
              {plural(s.unverified_source_count, "requirement")} couldn’t be matched to a quote in the
              brief. Check those first:{" "}
              <Link href={`${base}/requirements`} className="font-semibold text-brand hover:underline">
                review sources
              </Link>
              .
            </p>
          )}
        </Card>
      )}

      <Card className="p-0">
        <div className="px-5 pt-5 md:px-6 md:pt-6">
          <h2 className="text-xl font-extrabold text-ink">Agent runs</h2>
          <p className="mt-1 text-sm text-muted">Every Claude Code run is recorded, including failed ones and what they cost.</p>
        </div>
        <div className="mt-4 border-t border-line">
          <Runs name={name} />
        </div>
      </Card>
    </>
  );
}
