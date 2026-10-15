/** On a failed submit, bring the first problem into view (after React renders the errors). */
export function scrollToFirstProblem() {
  requestAnimationFrame(() => {
    document
      .querySelector('[role="alert"], [aria-invalid="true"]')
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}
