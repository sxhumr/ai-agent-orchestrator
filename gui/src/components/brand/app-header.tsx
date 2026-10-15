"use client";

import Link from "next/link";

import { cx } from "@/components/ui/primitives";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useHealth } from "@/lib/api/hooks";

export function Logo() {
  return (
    <span
      aria-hidden
      className="brand-gradient flex h-9 w-9 items-center justify-center rounded-full border border-line font-display text-sm font-extrabold text-white"
    >
      F
    </span>
  );
}

function ApiStatus() {
  const health = useHealth();
  const online = health.isSuccess;
  const label = health.isPending ? "Connecting…" : online ? "API connected" : "API offline";
  return (
    <span
      className="hidden items-center gap-2 rounded-full border border-line px-3 py-1.5 text-xs font-medium text-muted sm:flex"
      title={online ? undefined : "Start it with: uv run forgeflow serve"}
    >
      <span
        aria-hidden
        className={cx(
          "h-1.5 w-1.5 rounded-full",
          health.isPending && "bg-ink/20",
          online && "bg-brand-cyan",
          health.isError && "bg-red-500 dark:bg-red-400",
        )}
      />
      {label}
    </span>
  );
}

export function AppHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-2.5 md:px-8">
        <Link href="/" className="flex items-center gap-2.5 rounded-lg">
          <Logo />
          <span className="font-display text-sm font-bold tracking-tight text-ink">ForgeFlow</span>
        </Link>
        <div className="flex items-center gap-2">
          <ApiStatus />
          <ThemeToggle className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-muted transition-colors hover:text-ink" />
        </div>
      </div>
    </header>
  );
}
