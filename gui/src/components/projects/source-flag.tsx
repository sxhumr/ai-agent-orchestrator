"use client";

import { TickIcon, WarningIcon } from "@/components/ui/icons";
import { Badge } from "@/components/ui/primitives";
import type { Requirement } from "@/lib/api/types";
import { WARNING_TONE } from "@/lib/labels";

/** Whether a requirement's source quote was found verbatim in the brief. */
export function SourceFlag({ r }: { r: Requirement }) {
  if (r.origin === "developer") return <span className="text-xs text-muted">Added by you</span>;
  if (r.source?.quote_found)
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
        <TickIcon /> Quoted
      </span>
    );
  return (
    <Badge tone={WARNING_TONE}>
      <WarningIcon /> Unverified source
      <span className="sr-only">
        {r.source?.quote ? ": the quote wasn’t found in the brief" : ": the analyst gave no quote"}
      </span>
    </Badge>
  );
}
