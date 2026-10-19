export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Ask before throwing away typed text. Returns true when it's fine to discard. */
export function confirmDiscard(dirty: boolean, what = "your changes"): boolean {
  return !dirty || window.confirm(`Discard ${what}? This can’t be undone.`);
}

/** On a failed submit, bring the first problem into view (after React renders the errors). */
export function scrollToFirstProblem() {
  requestAnimationFrame(() => {
    document
      .querySelector('[role="alert"], [aria-invalid="true"]')
      ?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "center" });
  });
}
