import { Suspense } from "react";

import { ProjectShell } from "@/components/projects/project-shell";
import { InlinePending } from "@/components/ui/primitives";

// The project name is only known at request time. With Cache Components, reading it
// (useParams) must happen under Suspense so the static shell can prerender.
export default function ProjectLayout({ children }: LayoutProps<"/projects/[name]">) {
  return (
    <Suspense
      fallback={<InlinePending message="Loading project…" className="flex-1 py-24" />}
    >
      <ProjectShell>{children}</ProjectShell>
    </Suspense>
  );
}
