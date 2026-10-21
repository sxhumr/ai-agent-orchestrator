"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Button, Field, Input, Textarea } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { useCreateProject } from "@/lib/api/hooks";
import { confirmDiscard, scrollToFirstProblem } from "@/lib/forms";

const schema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Give the project a short name.")
    .max(100, "Keep the name under 100 characters.")
    .regex(
      /^[A-Za-z0-9][A-Za-z0-9._-]*$/,
      "Use letters, numbers, dots, dashes or underscores, starting with a letter or number.",
    ),
  root_path: z.string().trim().min(1, "Enter the folder the project lives in."),
  description: z.string().trim().max(500, "Keep the description under 500 characters."),
});

type Values = z.infer<typeof schema>;

export function NewProjectForm({ onCancel, autoFocus }: { onCancel?: () => void; autoFocus?: boolean }) {
  const router = useRouter();
  const create = useCreateProject();
  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors, isDirty },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    mode: "onBlur",
    defaultValues: { name: "", root_path: "", description: "" },
  });

  useEffect(() => {
    if (autoFocus) setFocus("name");
  }, [autoFocus, setFocus]);

  const cancel = () => {
    if (onCancel && confirmDiscard(isDirty, "this project")) onCancel();
  };

  const onSubmit = handleSubmit(
    (values) =>
      create.mutate(values, {
        onSuccess: (summary) => router.push(`/projects/${encodeURIComponent(summary.project.name)}/brief`),
      }),
    scrollToFirstProblem,
  );

  return (
    <form noValidate onSubmit={onSubmit} onKeyDown={(e) => e.key === "Escape" && onCancel && cancel()}>
      <fieldset disabled={create.isPending} className="space-y-5">
        <Field
          label="Project name"
          required
          error={errors.name?.message}
          hint="Used in URLs and on the command line, e.g. bike-repairs."
        >
          <Input
            {...register("name")}
            placeholder="bike-repairs"
            autoComplete="off"
            aria-invalid={!!errors.name}
          />
        </Field>
        <Field
          label="Project folder"
          required
          error={errors.root_path?.message}
          hint="An existing folder on this machine. ForgeFlow won’t change anything in it yet."
        >
          <Input
            {...register("root_path")}
            placeholder="~/code/bike-repairs"
            autoComplete="off"
            spellCheck={false}
            aria-invalid={!!errors.root_path}
          />
        </Field>
        <Field label="Description" error={errors.description?.message}>
          <Textarea {...register("description")} rows={2} aria-invalid={!!errors.description} />
        </Field>
      </fieldset>

      {create.isError && (
        <div className="mt-5">
          <Alert tone="error">{errorMessage(create.error)}</Alert>
        </div>
      )}

      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-ink/10 pt-5 sm:flex-row sm:justify-end">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={cancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" loading={create.isPending}>
          Create project
        </Button>
      </div>
    </form>
  );
}
