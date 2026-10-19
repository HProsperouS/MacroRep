import type { Proposal } from "@/types/coach"

/** What "Apply all" changed, by the kinds of proposal it applied. */
export function appliedDescription(applied: Proposal[]) {
  const nutrition = applied.some((proposal) => proposal.kind === "nutrition")
  const training = applied.some((proposal) => proposal.kind === "training")
  if (nutrition && training) return "Your daily targets and routines are updated."
  return training ? "Your routines are updated." : "Your daily targets are updated."
}
