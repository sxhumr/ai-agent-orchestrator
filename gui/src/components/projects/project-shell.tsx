"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useState } from "react";

import { ArrowLeftIcon, TickIcon } from "@/components/ui/icons";
import {
  Badge,
  Button,
  Card,
  CardError,
  Chip,
  cx,
  InlinePending,
} from "@/components/ui/primitives";
import { ApiError, errorMessage } from "@/lib/api/client";
import { useProject } from "@/lib/api/hooks";
import type { ProjectSummary } from "@/lib/api/types";
import { PROJECT_STATUS_LABEL, PROJECT_STATUS_TONE } from "@/lib/labels";

export function useProjectName(): string {
  return decodeURIComponent(useParams<{ name: string }>().name);
}

type StepState = "done" | "attention" | "active" | "idle";

interface Step {
  href: string;
  label: string;
  detail: string;
  state: StepState;
  count?: number;
}

function steps(base: string, s: ProjectSummary): Step[] {
  const hasBrief = s.brief_version !== null;
  const hasReqs = s.requirement_count > 0;
  const accepted = s.requirements_by_status.accepted ?? 0;
  return [
    {
      href: `${base}/brief`,
      label: "Brief",
      detail: hasBrief ? `Version ${s.brief_version}` : "Add what the client wants",
      state: hasBrief ? "done" : "idle",
    },
    {
      href: `${base}/requirements`,
      label: "Requirements",
      detail: hasReqs ? `${accepted} of ${s.requirement_count} accepted` : "Generate from the brief",
      state: hasReqs && accepted === s.requirement_count ? "done" : "idle",
      count: s.requirement_count || undefined,
    },
    {
      href: `${base}/questions`,
      label: "Questions",
      detail: !hasReqs
        ? "Raised during analysis"
        : s.open_item_count
          ? "Needs your answers"
          : "All answered",
      state: !hasReqs ? "idle" : s.open_item_count ? "attention" : "done",
      count: s.open_item_count || undefined,
    },
  ];
}

const CIRCLE: Record<StepState, string> = {
  done: "bg-brand text-white",
  attention: "bg-brand-orange text-white",
  active: "bg-brand/10 text-brand",
  idle: "bg-ink/5 text-muted",
};

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cx(
        "relative flex min-h-11 items-center gap-3 rounded-lg px-2.5 py-2 transition-colors hover:bg-brand/5",
        active &&
          "bg-brand/5 before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-brand",
      )}
    >
      {children}
    </Link>
  );
}

function ProjectNav({ summary, base }: { summary: ProjectSummary; base: string }) {
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
  return (
    <nav aria-label="Project sections" className="space-y-1">
      <NavLink href={base} active={pathname === base}>
        <span className={cx("text-sm", pathname === base ? "font-semibold text-brand" : "text-ink")}>
          Overview
        </span>
      </NavLink>
      <ol className="space-y-1">
        {steps(base, summary).map((step, i) => {
          const active = isActive(step.href);
          const state = active && step.state === "idle" ? "active" : step.state;
          return (
            <li key={step.href}>
              <NavLink href={step.href} active={active}>
                <span
                  className={cx(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums transition-colors",
                    CIRCLE[state],
                  )}
                >
                  {state === "done" ? <TickIcon /> : i + 1}
                </span>
                <span className="min-w-0 flex-1 leading-snug">
                  <span className={cx("block text-sm", active ? "font-semibold text-brand" : "text-ink")}>
                    {step.label}
                    {state === "attention" && <span className="sr-only"> (needs attention)</span>}
                  </span>
                  <span className="block text-xs text-muted">{step.detail}</span>
                </span>
                {step.count !== undefined && <Chip emphasis={state === "attention"}>{step.count}</Chip>}
              </NavLink>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function ProjectShell({ children }: { children: React.ReactNode }) {
  const name = useProjectName();
  const project = useProject(name);
  const [navOpen, setNavOpen] = useState(false);
  const base = `/projects/${encodeURIComponent(name)}`;

  if (project.isError) {
    const missing = project.error instanceof ApiError && project.error.status === 404;
    return (
      <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 p-4 md:p-8">
        {missing ? (
          <Card>
            <h1 className="text-2xl font-extrabold text-ink">We can’t find “{name}”</h1>
            <p className="mt-1 text-sm text-muted">
              It may have been created against a different database. Pick a project from the list.
            </p>
            <Link
              href="/"
              className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-xl border border-line bg-surface px-5 text-sm font-semibold text-ink transition-colors hover:border-brand/40 hover:text-brand"
            >
              <ArrowLeftIcon /> All projects
            </Link>
          </Card>
        ) : (
          <CardError message={errorMessage(project.error)} onRetry={() => project.refetch()} />
        )}
      </main>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 p-4 md:flex-row md:p-8">
      <aside className="w-full shrink-0 md:w-72">
        <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm shadow-ink/[0.03] md:sticky md:top-20">
          <div className="flex items-start justify-between gap-2 px-2.5 pt-1.5 pb-3">
            <div className="min-w-0">
              <Link href="/" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-ink">
                <ArrowLeftIcon className="h-3.5 w-3.5" /> All projects
              </Link>
              <p className="mt-1 truncate font-display text-lg font-extrabold text-ink" title={name}>
                {name}
              </p>
              {project.data && (
                <div className="mt-1.5">
                  <Badge tone={PROJECT_STATUS_TONE[project.data.project.status]}>
                    {PROJECT_STATUS_LABEL[project.data.project.status]}
                  </Badge>
                </div>
              )}
            </div>
            <Button
              variant="secondary"
              className="px-3 py-1.5 text-xs md:hidden"
              aria-expanded={navOpen}
              aria-controls="project-nav"
              onClick={() => setNavOpen((open) => !open)}
            >
              {navOpen ? "Hide sections" : "Sections"}
            </Button>
          </div>
          <div id="project-nav" className={cx("border-t border-line pt-3", !navOpen && "hidden md:block")}>
            {project.data ? (
              <ProjectNav summary={project.data} base={base} />
            ) : (
              <InlinePending message="Loading sections…" />
            )}
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 space-y-6">{children}</main>
    </div>
  );
}
