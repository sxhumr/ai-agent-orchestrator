import { Suspense } from "react";

import { ProjectShell } from "@/components/projects/project-shell";

// The project name is only known at request time. With Cache Components, reading it
// (useParams) must happen under Suspense so the static shell can prerender.
export default function ProjectLayout({ children }: LayoutProps<"/projects/[name]">) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center gap-2 py-24 text-sm text-muted">
          Loading project…
        </div>
      }
    >
      <ProjectShell>{children}</ProjectShell>
    </Suspense>
  );
}
