import type { Proposal } from "@/types/coach"

export function nutritionProposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "p1",
    kind: "nutrition",
    headline: "Raise calories slightly",
    changes: [{ id: "calories", label: "Daily calories", unit: "kcal", before: 2000, after: 2100, step: 50 }],
    evidence: ["Averaged 1,850 kcal against a 2,000 target"],
    reviewerNote: "Within the weekly limit.",
    status: "pending",
    ...overrides,
  }
}
