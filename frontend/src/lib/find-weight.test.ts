import { describe, expect, it } from "vitest"

import { adviseWeight, findWeightStep } from "@/lib/find-weight"

describe("adviseWeight", () => {
  it.each([
    // [weight, rpe, next weight, direction]
    [40, 5, 42.5, "up"], // three points easy: 9% of 40 kg is 3.6, to the nearest 2.5 kg step
    [40, 7, 42.5, "up"], // one point easy is under a step, but still moves one
    [100, 7, 102.5, "up"],
    [100, 8, 100, "hold"],
    [100, 8.5, 100, "hold"],
    [100, 7.5, 100, "hold"],
    [100, 9, 97.5, "down"],
    [100, 10, 95, "down"], // two points hard: 6% of 100 kg
    [60, 6, 62.5, "up"], // two points easy: 6% of 60 kg is 3.6, to the nearest 2.5 kg step
    [200, 6, 212.5, "up"], // two points easy: 6% of 200 kg is 12, to the nearest 2.5 kg step
  ])("%s kg at RPE %s goes to %s kg (%s)", (weight, rpe, next, direction) => {
    const advice = adviseWeight(weight, rpe)
    expect(advice).not.toBeNull()
    expect(advice?.weightKg).toBe(next)
    expect(advice?.direction).toBe(direction)
  })

  it("never moves the load more than 15% in one go", () => {
    expect(adviseWeight(100, 1)?.weightKg).toBe(115)
  })

  it("never suggests nothing on the bar", () => {
    expect(adviseWeight(2.5, 10)?.weightKg).toBe(2.5)
  })

  it.each([
    [0, 7],
    [-5, 7],
    [60, 0],
    [60, 11],
    [60, Number.NaN],
  ])("has no advice for %s kg at RPE %s", (weight, rpe) => {
    expect(adviseWeight(weight, rpe)).toBeNull()
  })

  it("says why and what to try in its message", () => {
    expect(adviseWeight(100, 9)?.message).toBe("RPE 9 was close to your limit. Try 97.5 kg.")
    expect(adviseWeight(100, 8)?.message).toBe("RPE 8 is about right. Stay at 100 kg.")
  })
})

const set = (over: Partial<{ kind: string; weight: string; reps: string; rpe: string; done: boolean }> = {}) => ({
  kind: "working",
  weight: "",
  reps: "8",
  rpe: "",
  done: false,
  ...over,
})

describe("findWeightStep", () => {
  it("starts by asking for a light first set, for the planned reps", () => {
    expect(findWeightStep([set(), set()])).toEqual({ step: "start", reps: 8 })
    expect(findWeightStep([set({ reps: "" })])).toEqual({ step: "start", reps: null })
  })

  it("asks for an RPE once a set is done without one", () => {
    expect(findWeightStep([set({ weight: "40", done: true }), set()])).toEqual({ step: "rate" })
  })

  it("advises from the latest set done", () => {
    const step = findWeightStep([
      set({ weight: "40", rpe: "5", done: true }),
      set({ weight: "45", rpe: "9", done: true }),
      set(),
    ])
    expect(step).toMatchObject({ step: "advice", advice: { weightKg: 42.5, direction: "down" } })
  })

  it("ignores warm-ups", () => {
    expect(findWeightStep([set({ kind: "warmup", weight: "20", rpe: "5", done: true }), set()])).toEqual({
      step: "start",
      reps: 8,
    })
  })

  it("has nothing to say for a bodyweight set", () => {
    expect(findWeightStep([set({ weight: "0", rpe: "7", done: true })])).toBeNull()
  })
})
