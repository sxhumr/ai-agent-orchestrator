"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AnalysisPanel } from "@/components/projects/analysis-panel";
import { useProjectName } from "@/components/projects/project-shell";
import {
  Alert,
  Button,
  Card,
  CardError,
  CardPending,
  cx,
  Field,
  Input,
  PageHeader,
  PageTitle,
  RelativeTime,
  Textarea,
} from "@/components/ui/primitives";
import { TickIcon } from "@/components/ui/icons";
import { errorMessage } from "@/lib/api/client";
import { useAddBrief, useBriefs, useProject } from "@/lib/api/hooks";
import type { Brief } from "@/lib/api/types";
import { confirmDiscard, scrollToFirstProblem } from "@/lib/forms";

const schema = z.object({
  content: z
    .string()
    .trim()
    .min(40, "A useful brief is at least a few sentences. Describe who it’s for and what they need."),
  source_name: z.string().trim().max(200, "Keep the source under 200 characters."),
});

type Values = z.infer<typeof schema>;

function BriefForm({
  name,
  previous,
  onDone,
  onCancel,
}: {
  name: string;
  previous?: string;
  onDone?: (version: number) => void;
  onCancel?: () => void;
}) {
  const add = useAddBrief(name);
  const {
    register,
    handleSubmit,
    reset,
    setFocus,
    formState: { errors, isDirty },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: { content: previous ?? "", source_name: "" },
  });

  useEffect(() => {
    if (onCancel) setFocus("content");
  }, [onCancel, setFocus]);

  const cancel = () => {
    if (onCancel && confirmDiscard(isDirty, "this draft")) onCancel();
  };

  return (
    <form
      noValidate
      onKeyDown={(e) => e.key === "Escape" && onCancel && cancel()}
      onSubmit={handleSubmit(
        (values) =>
          add.mutate(
            { content: values.content, source_name: values.source_name || null },
            {
              onSuccess: (brief) => {
                reset({ content: "", source_name: "" });
                onDone?.(brief.version);
              },
            },
          ),
        scrollToFirstProblem,
      )}
    >
      <fieldset disabled={add.isPending} className="mt-6 space-y-5">
        <Field
          label="Brief"
          required
          error={errors.content?.message}
          hint="Paste it as written. Requirements quote this text, so don’t tidy away the client’s wording."
        >
          <Textarea {...register("content")} rows={14} aria-invalid={!!errors.content} />
        </Field>
        <Field label="Source" error={errors.source_name?.message} hint="Optional, e.g. the email or document it came from.">
          <Input {...register("source_name")} placeholder="Kick-off email, 12 Oct" aria-invalid={!!errors.source_name} />
        </Field>
      </fieldset>
      {add.isError && (
        <div className="mt-5">
          <Alert tone="error">{errorMessage(add.error)}</Alert>
        </div>
      )}
      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-ink/10 pt-5 sm:flex-row sm:justify-end">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={cancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={add.isPending}>
          {previous === undefined ? "Save the brief" : "Save as a new version"}
        </Button>
      </div>
    </form>
  );
}

function BriefViewer({ briefs, name }: { briefs: Brief[]; name: string }) {
  const latest = briefs[briefs.length - 1];
  const [selected, setSelected] = useState<number>(latest.version);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState<number | null>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const savedAlert = useRef<HTMLDivElement>(null);
  const wasEditing = useRef(false);
  const brief = briefs.find((b) => b.version === selected) ?? latest;

  // Focus follows the outcome: the confirmation after a save, the button after Cancel.
  useEffect(() => {
    if (wasEditing.current && !editing) (saved ? savedAlert.current : editButton.current)?.focus();
    wasEditing.current = editing;
  }, [editing, saved]);

  if (editing) {
    return (
      <Card>
        <h2 className="text-xl font-extrabold text-ink">New brief version</h2>
        <p className="mt-1 text-sm text-muted">
          Version {latest.version} stays in the history. Requirements keep pointing at the version they
          were generated from.
        </p>
        <BriefForm
          name={name}
          previous={latest.content}
          onCancel={() => {
            setSaved(null);
            setEditing(false);
          }}
          onDone={(version) => {
            setSaved(version);
            setEditing(false);
            setSelected(Number.MAX_SAFE_INTEGER); // jump to the newest version once it loads
          }}
        />
      </Card>
    );
  }

  return (
    <Card>
      {saved !== null && (
        <div className="mb-5">
          <Alert ref={savedAlert} tone="success" title={`Brief v${saved} saved`}>
            Earlier versions stay in the history below.
          </Alert>
        </div>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-xl font-extrabold text-ink">Brief v{brief.version}</h2>
          <p className="mt-1 text-sm break-words text-muted">
            Added <RelativeTime iso={brief.created_at} />
            {brief.source_name && <> from {brief.source_name}</>}
            {brief.version !== latest.version && " · an older version"}
          </p>
        </div>
        <Button
          ref={editButton}
          variant="secondary"
          className="shrink-0 whitespace-nowrap"
          onClick={() => setEditing(true)}
        >
          Edit as new version
        </Button>
      </div>
      {briefs.length > 1 && (
        <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Brief versions">
          {[...briefs].reverse().map((b) => (
            <button
              key={b.version}
              type="button"
              aria-pressed={b.version === brief.version}
              onClick={() => setSelected(b.version)}
              className={cx(
                "inline-flex min-h-11 items-center gap-1.5 rounded-lg border px-3.5 text-sm font-semibold tabular-nums transition-colors",
                b.version === brief.version
                  ? "border-brand/40 bg-brand/5 text-brand"
                  : "border-line bg-surface text-muted hover:text-ink",
              )}
            >
              {b.version === brief.version && <TickIcon />}
              v{b.version}
              {b.version === latest.version && " · latest"}
            </button>
          ))}
        </div>
      )}
      <div className="mt-6 rounded-lg border border-line bg-surface-2 p-4 md:p-5">
        <p className="max-w-prose whitespace-pre-wrap text-sm leading-relaxed text-ink">{brief.content}</p>
      </div>
    </Card>
  );
}

export default function BriefPage() {
  const name = useProjectName();
  const project = useProject(name);
  const briefs = useBriefs(name);

  return (
    <>
      <PageTitle parts={[name, "Brief"]} />
      <PageHeader
        eyebrow="Step 1"
        title="Business brief"
        description="What the client wants, in their words. Every requirement links back to the exact version and sentence it came from."
      />
      {briefs.isPending && <CardPending message="Loading the brief…" />}
      {briefs.isError && <CardError message={errorMessage(briefs.error)} onRetry={() => briefs.refetch()} />}
      {briefs.isSuccess && briefs.data.length === 0 && (
        <Card>
          <h2 className="text-xl font-extrabold text-ink">Add the brief</h2>
          <p className="mt-1 text-sm text-muted">
            A few paragraphs is enough: who it’s for, what they need to do, and any constraints like
            logins, budgets or deadlines.
          </p>
          <BriefForm name={name} />
        </Card>
      )}
      {briefs.isSuccess && briefs.data.length > 0 && <BriefViewer briefs={briefs.data} name={name} />}
      {project.data && <AnalysisPanel name={name} summary={project.data} />}
    </>
  );
}
