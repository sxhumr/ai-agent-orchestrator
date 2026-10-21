"use client";

import { cloneElement, forwardRef, isValidElement, useId } from "react";

import { ERROR_TONE, SUCCESS_TONE, WARNING_TONE } from "@/lib/labels";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

const PRIMARY = "bg-brand-fill text-white shadow-sm shadow-brand/25 hover:bg-brand-deep";
const PRESS = "transition-all active:scale-[0.98] motion-reduce:active:scale-100";

/** Classes for a link that looks like the primary Button. */
export const primaryLinkClass = cx(
  "inline-flex min-h-11 items-center justify-center rounded-xl px-5 text-sm font-semibold",
  PRIMARY,
  PRESS,
);

/** Classes for a link that looks like the secondary Button. */
export const secondaryLinkClass = cx(
  "inline-flex min-h-11 items-center justify-center rounded-xl border border-line bg-surface px-5 text-sm font-semibold text-ink hover:border-brand/40 hover:text-brand",
  PRESS,
);

/** Small inline text link with a 44px hit area that doesn't shift the text. */
export const textLinkClass =
  "-mx-2 inline-flex min-h-11 items-center rounded-lg px-2 font-medium text-brand hover:underline";

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
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 text-sm font-semibold",
        PRESS,
        "disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && PRIMARY,
        variant === "secondary" && "border border-line bg-surface text-ink hover:border-brand/40 hover:text-brand",
        variant === "ghost" && "text-muted hover:text-ink",
        className,
      )}
      {...props}
    >
      {loading && (
        <Spinner
          decorative
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

/** `decorative` spinners sit next to text that already says what's happening. */
export function Spinner({ className, decorative }: { className?: string; decorative?: boolean }) {
  return (
    <span
      className={cx(
        "inline-block shrink-0 animate-spin rounded-full border-2 border-brand/25 border-t-brand",
        className ?? "h-5 w-5",
      )}
      {...(decorative ? { "aria-hidden": true } : { role: "status", "aria-label": "Loading" })}
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
  const id = useId();
  const noteId = `${id}-note`;
  const note = error ?? hint;
  // The control gets the id, the hint or error as its description, and the
  // required state, so the label stays just the label for screen readers.
  const control = isValidElement<Record<string, unknown>>(children)
    ? cloneElement(children, {
        id: (children.props.id as string | undefined) ?? id,
        "aria-describedby": note ? noteId : undefined,
        "aria-required": required || undefined,
      })
    : children;
  const controlId =
    isValidElement<Record<string, unknown>>(children) && typeof children.props.id === "string"
      ? children.props.id
      : id;
  return (
    <div>
      <label htmlFor={controlId} className="mb-1.5 flex items-baseline gap-1 text-sm font-medium text-ink">
        {label}
        {required && (
          <span aria-hidden className="text-brand">
            *
          </span>
        )}
      </label>
      {control}
      {hint && !error && (
        <p id={noteId} className="mt-1.5 text-[13px] leading-snug text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p
          id={noteId}
          role="alert"
          className="mt-1.5 text-[13px] font-medium leading-snug text-red-600 dark:text-red-400"
        >
          {error}
        </p>
      )}
    </div>
  );
}

export const Alert = forwardRef<
  HTMLDivElement,
  {
    tone?: "error" | "info" | "success" | "warning";
    title?: string;
    children: React.ReactNode;
  }
>(function Alert({ tone = "error", title, children }, ref) {
  const tones = {
    error: ERROR_TONE,
    info: "border-brand/15 bg-brand/[0.04] text-ink dark:bg-brand/10",
    success: SUCCESS_TONE,
    warning: WARNING_TONE,
  };
  return (
    <div
      ref={ref}
      tabIndex={ref ? -1 : undefined}
      role={tone === "error" ? "alert" : "status"}
      className={cx("rounded-xl border px-4 py-3 text-sm leading-relaxed", tones[tone])}
    >
      {title && <p className="mb-0.5 font-semibold">{title}</p>}
      {children}
    </div>
  );
});

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
    <div
      role="status"
      className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface py-20 shadow-sm shadow-ink/[0.03]"
    >
      <Spinner decorative />
      <p className="text-sm text-muted">{message}</p>
    </div>
  );
}

/** Pending state inline or in a sidebar. */
export function InlinePending({ message, className }: { message: string; className?: string }) {
  return (
    <div role="status" className={cx("flex items-center justify-center gap-2 text-sm text-muted", className ?? "py-8")}>
      <Spinner decorative className="h-4 w-4" /> {message}
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
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h1 className={cx("text-2xl font-extrabold text-ink", eyebrow ? "mt-1" : undefined)}>{title}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="font-display text-xs font-bold uppercase tracking-wider text-muted">{children}</p>;
}

/** Sets the tab title, which is also what screen readers announce on navigation. */
export function PageTitle({ parts }: { parts: (string | undefined)[] }) {
  return <title>{[...parts.filter(Boolean), "ForgeFlow"].join(" · ")}</title>;
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
