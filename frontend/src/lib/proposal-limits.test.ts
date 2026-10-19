import { describe, expect, it } from "vitest"

import { editedValueError } from "@/lib/proposal-limits"
import type { ProposalChange } from "@/types/coach"

function change(unit: ProposalChange["unit"], before: number, after: number): ProposalChange {
  return { id: "c", label: "Change", unit, before, after, step: 1 }
}

describe("editedValueError", () => {
  it("accepts a training change the server proposed, even when it's a large share", () => {
    // 3 → 4 sets is +33%: fine, because sets move one at a time.
    expect(editedValueError(change("sets", 3, 4), "4")).toBeUndefined()
    expect(editedValueError(change("reps", 8, 11), "11")).toBeUndefined()
  })

  it.each([
    ["sets", 3, "5", "Change it by at most 1 from 3 sets"],
    ["sets", 3, "3.5", "Enter a whole number"],
    ["sets", 1, "0", "Must be at least 1"],
    ["reps", 8, "12", "Change it by at most 3 from 8 reps"],
    ["reps", 28, "31", "Must be 30 or less"],
    ["kg", 100, "111", "Stay within 10% of 100 kg"],
    ["kg", 100, "-5", "Can’t be negative"],
    ["kcal", 2000, "2600", "Stay within 25% of 2,000"],
    ["kcal", 2000, "", "Enter a number"],
  ] as const)("refuses %s from %d to %s", (unit, before, raw, message) => {
    expect(editedValueError(change(unit, before, before), raw)).toBe(message)
  })

  it("accepts the edge of each limit", () => {
    expect(editedValueError(change("kg", 100, 95), "110")).toBeUndefined()
    expect(editedValueError(change("kg", 100, 95), "90")).toBeUndefined()
    expect(editedValueError(change("kcal", 2000, 2100), "2500")).toBeUndefined()
  })
})
