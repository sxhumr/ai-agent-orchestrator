"use client";

import { forwardRef } from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export const Button = forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "ghost";
    loading?: boolean;
  }
>(function Button({ variant = "primary", loading, className, children, disabled, ...props }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-semibold transition-all",
        "disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]",
        variant === "primary" && "bg-brand text-white shadow-sm shadow-brand/25 hover:bg-brand-deep",
        variant === "secondary" && "border border-line bg-surface text-ink hover:border-brand/40 hover:text-brand",
        variant === "ghost" && "text-muted hover:text-ink",
        className,
      )}
      {...props}
    >
      {loading && (
        <Spinner
          className={cx(
            "h-4 w-4",
            variant === "primary" ? "border-white/40 border-t-white" : "border-brand/25 border-t-brand",
          )}
        />
      )}
      {children}
    </button>
  );
});

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cx(
        "inline-block animate-spin rounded-full border-2 border-brand/25 border-t-brand",
        className ?? "h-5 w-5",
      )}
      role="status"
      aria-label="Loading"
    />
  );
}

// Shared control skin. Height is applied per-component so `min-h-*` classes
// never collide in one string (utility order in the string doesn't decide the winner).
const CONTROL =
  "w-full rounded-xl border border-field-line bg-surface px-3.5 text-[15px] text-ink transition-colors " +
  "placeholder:text-muted/70 hover:border-muted/70 " +
  "focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/10 " +
  "disabled:bg-background disabled:text-muted read-only:bg-background " +
  "aria-[invalid=true]:border-red-500 aria-[invalid=true]:focus:ring-red-100 dark:aria-[invalid=true]:focus:ring-red-900/40";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cx("min-h-11", CONTROL, className)} {...props} />;
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, rows = 4, ...props }, ref) {
  return <textarea ref={ref} rows={rows} className={cx(CONTROL, "py-2.5", className)} {...props} />;
});

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <select ref={ref} className={cx("min-h-11", CONTROL, className)} {...props}>
        {children}
      </select>
    );
  },
);

export function Field({
  label,
  error,
  hint,
  children,
  required,
}: {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline gap-1 text-sm font-medium text-ink">
        {label}
        {required && (
          <span aria-hidden className="text-brand">
            *
          </span>
        )}
      </span>
      {children}
      {hint && !error && <span className="mt-1.5 block text-[13px] leading-snug text-muted">{hint}</span>}
      {error && (
        <span
          role="alert"
          className="mt-1.5 block text-[13px] font-medium leading-snug text-red-600 dark:text-red-400"
        >
          {error}
        </span>
      )}
    </label>
  );
}

export function Alert({
  tone = "error",
  title,
  children,
}: {
  tone?: "error" | "info" | "success" | "warning";
  title?: string;
  children: React.ReactNode;
}) {
  const tones = {
    error: "border-red-200 bg-red-50 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300",
    info: "border-brand/15 bg-brand/[0.04] text-ink dark:bg-brand/10",
    success:
      "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300",
    warning:
      "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300",
  };
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx("rounded-xl border px-4 py-3 text-sm leading-relaxed", tones[tone])}
    >
      {title && <p className="mb-0.5 font-semibold">{title}</p>}
      {children}
    </div>
  );
}

export function Checkbox({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: React.ReactNode }) {
  return (
    <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-field-line bg-surface px-3.5 py-2.5 text-sm text-ink transition-colors hover:border-brand/40 has-checked:border-brand/50 has-checked:bg-brand/[0.03]">
      <input
        type="checkbox"
        className="h-4.5 w-4.5 shrink-0 rounded border-field-line accent-[var(--brand-blue)]"
        {...props}
      />
      <span className="leading-snug">{label}</span>
    </label>
  );
}

/** The one card recipe. Use it instead of re-typing the classes. */
export function Card({
  className,
  children,
  as: Tag = "div",
}: {
  className?: string;
  children: React.ReactNode;
  as?: "div" | "section" | "article";
}) {
  return (
    <Tag className={cx("rounded-2xl border border-line bg-surface shadow-sm shadow-ink/[0.03]", className ?? "p-5 md:p-8")}>
      {children}
    </Tag>
  );
}

/** Status badge. Tones come from a Record in lib/labels.ts, never from the call site. */
export function Badge({ tone, children }: { tone: string; children: React.ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap",
        tone,
      )}
    >
      {children}
    </span>
  );
}

export function Chip({ emphasis, children }: { emphasis?: boolean; children: React.ReactNode }) {
  return (
    <span
      className={cx(
        "rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums",
        emphasis ? "bg-brand/10 text-brand" : "bg-ink/5 text-muted",
      )}
    >
      {children}
    </span>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm shadow-ink/[0.03]">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 font-display text-2xl font-extrabold text-ink tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Pending state inside a card slot. */
export function CardPending({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface py-20 shadow-sm shadow-ink/[0.03]">
      <Spinner />
      <p className="text-sm text-muted">{message}</p>
    </div>
  );
}

/** Pending state inline or in a sidebar. */
export function InlinePending({ message, className }: { message: string; className?: string }) {
  return (
    <div className={cx("flex items-center justify-center gap-2 text-sm text-muted", className ?? "py-8")}>
      <Spinner className="h-4 w-4" /> {message}
    </div>
  );
}

/** Error state: a human sentence plus a way out. */
export function CardError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-sm shadow-ink/[0.03]">
      <Alert tone="error">{message}</Alert>
      <Button variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-wider text-muted">{eyebrow}</p>}
        <h1 className={cx("text-2xl font-extrabold text-ink", eyebrow ? "mt-1" : undefined)}>{title}</h1>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function RelativeTime({ iso }: { iso: string }) {
  const date = new Date(iso);
  return (
    <time dateTime={iso} title={date.toLocaleString()} className="tabular-nums">
      {date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}{" "}
      {date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
    </time>
  );
}
