import { describe, expect, it } from "vitest"

import { bandRepsSuffix, bodyWeightNote, setLoadLabel } from "@/lib/load-labels"

describe("load labels", () => {
  it("shows bodyweight sets as BW plus what was added, and band sets by reps", () => {
    expect(setLoadLabel("barbell", 60, 8)).toBe("60 kg × 8")
    expect(setLoadLabel("bodyweight", 0, 12)).toBe("BW × 12")
    expect(setLoadLabel("bodyweight", 10, 8)).toBe("BW + 10 kg × 8")
    expect(setLoadLabel("band", 20, 15)).toBe("Band × 15")
    expect(setLoadLabel(null, 40, 5)).toBe("40 kg × 5")
  })

  it("mentions band reps and the bodyweight used only when there are some", () => {
    expect(bandRepsSuffix(0)).toBe("")
    expect(bandRepsSuffix(45)).toBe(" · 45 band reps")
    expect(bodyWeightNote(72, [{ equipment: "bodyweight" }])).toBe("Bodyweight counted at 72 kg")
    expect(bodyWeightNote(72, [{ equipment: "barbell" }])).toBeNull()
    expect(bodyWeightNote(null, [{ equipment: "bodyweight" }])).toBeNull()
  })
})
