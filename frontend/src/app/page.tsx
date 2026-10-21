"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { NewProjectForm } from "@/components/projects/new-project-form";
import { PlusIcon } from "@/components/ui/icons";
import {
  Badge,
  Button,
  Card,
  CardError,
  CardPending,
  Chip,
  PageHeader,
  PageTitle,
} from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { useProjects } from "@/lib/api/hooks";
import type { ProjectSummary } from "@/lib/api/types";
import { formatUsd, plural, PROJECT_STATUS_LABEL, PROJECT_STATUS_TONE } from "@/lib/labels";

function ProjectCard({ summary }: { summary: ProjectSummary }) {
  const { project } = summary;
  const accepted = summary.requirements_by_status.accepted ?? 0;
  return (
    // Stretched link: the whole card is clickable, but the link's accessible
    // name is just the project name rather than everything in the card.
    <li className="relative h-full min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-sm shadow-ink/[0.03] transition-colors hover:border-brand/40 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-brand">
      <div className="flex items-start justify-between gap-3">
        <h2 className="truncate font-display text-lg font-extrabold text-ink" title={project.name}>
          <Link
            href={`/projects/${encodeURIComponent(project.name)}`}
            className="outline-none after:absolute after:inset-0 after:rounded-2xl"
          >
            {project.name}
          </Link>
        </h2>
        <Badge tone={PROJECT_STATUS_TONE[project.status]}>{PROJECT_STATUS_LABEL[project.status]}</Badge>
      </div>
      <p className="mt-1 line-clamp-2 text-sm text-muted">
        {project.description || <span className="italic">No description</span>}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Chip>{summary.brief_version ? `Brief v${summary.brief_version}` : "No brief yet"}</Chip>
        {summary.requirement_count > 0 && (
          <Chip>
            {accepted} of {plural(summary.requirement_count, "requirement")} accepted
          </Chip>
        )}
        {summary.open_item_count > 0 && (
          <Chip emphasis>{plural(summary.open_item_count, "open question")}</Chip>
        )}
        {summary.total_cost_usd > 0 && <Chip>{formatUsd(summary.total_cost_usd)} spent</Chip>}
      </div>
      <p className="mt-4 truncate text-xs text-muted" title={project.root_path}>
        {project.root_path}
      </p>
    </li>
  );
}

export default function HomePage() {
  const projects = useProjects();
  const [creating, setCreating] = useState(false);
  const newButton = useRef<HTMLButtonElement>(null);
  const wasCreating = useRef(false);

  // Hand focus back to "New project" when the form closes.
  useEffect(() => {
    if (wasCreating.current && !creating) newButton.current?.focus();
    wasCreating.current = creating;
  }, [creating]);

  return (
    <main id="main" className="mx-auto w-full max-w-6xl flex-1 space-y-6 p-4 md:p-8">
      <PageTitle parts={["Projects"]} />
      <PageHeader
        title="Your projects"
        description="Each project starts from a business brief. ForgeFlow turns it into requirements you can review, question and approve."
        actions={
          !creating &&
          (projects.data?.length ?? 0) > 0 && (
            <Button ref={newButton} onClick={() => setCreating(true)}>
              <PlusIcon /> New project
            </Button>
          )
        }
      />

      {creating && (
        <Card>
          <h2 className="text-xl font-extrabold text-ink">New project</h2>
          <p className="mt-1 mb-6 text-sm text-muted">
            Point ForgeFlow at the folder the software will live in. You’ll add the brief next.
          </p>
          <NewProjectForm autoFocus onCancel={() => setCreating(false)} />
        </Card>
      )}

      {projects.isPending && <CardPending message="Loading your projects…" />}

      {projects.isError && (
        <CardError message={errorMessage(projects.error)} onRetry={() => projects.refetch()} />
      )}

      {projects.isSuccess && projects.data.length === 0 && !creating && (
        <Card>
          <h2 className="text-xl font-extrabold text-ink">Start your first project</h2>
          <p className="mt-1 mb-6 max-w-xl text-sm text-muted">
            You’ll need a folder for the project and a business brief: a few paragraphs describing
            what the client wants. Analysis takes about a minute and usually costs well under $0.50.
          </p>
          <NewProjectForm />
        </Card>
      )}

      {projects.isSuccess && projects.data.length > 0 && (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.map((summary) => (
            <ProjectCard key={summary.project.id} summary={summary} />
          ))}
        </ul>
      )}
    </main>
  );
}
