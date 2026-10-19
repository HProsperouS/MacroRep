import { describe, expect, it } from "vitest"

import {
  historySetLabels,
  initSession,
  isSetCompletable,
  parseRpe,
  sessionReducer,
  sessionTotals,
  setLabels,
  toFinishInput,
  type SessionState,
} from "@/lib/workout-session"
import type { PlannedWorkout, SetKind } from "@/types/workout"

const plan: PlannedWorkout = {
  id: "plan-1",
  name: "Push day",
  weekLabel: "Week 1",
  estimatedMinutes: 45,
  exercises: [
    {
      id: "bench",
      name: "Bench Press",
      equipment: "Barbell",
      muscles: "Chest",
      restSeconds: 120,
      sets: [
        { id: "bench-0", kind: "warmup", targetWeightKg: 40, targetReps: 10 },
        { id: "bench-1", kind: "working", targetWeightKg: 60, targetReps: 8 },
      ],
    },
  ],
}

function started(): SessionState {
  return initSession(plan)
}

describe("initSession", () => {
  it("pre-fills sets from the plan's targets", () => {
    const session = started()
    expect(session.planId).toBe("plan-1")
    expect(session.exercises[0].sets.map((set) => [set.kind, set.weight, set.reps, set.done])).toEqual([
      ["warmup", "40", "10", false],
      ["working", "60", "8", false],
    ])
  })

  it("starts an empty freestyle workout without a plan", () => {
    expect(initSession(null)).toMatchObject({ planId: null, exercises: [] })
  })
})

describe("set labels", () => {
  const kinds = (...list: SetKind[]) => list.map((kind) => ({ kind }))

  it("letters warm-up, failure and drop sets and numbers working sets", () => {
    expect(setLabels(kinds("warmup", "working", "failure", "drop", "working"))).toEqual(["W", "1", "F", "D", "2"])
  })

  it("spells out the kind in history, numbering only working sets", () => {
    expect(historySetLabels(kinds("warmup", "working", "failure", "drop", "working"))).toEqual(["Warm-up", "Set 1", "Failure", "Drop set", "Set 2"])
  })
})

describe("set validation", () => {
  it("accepts a weight of 0 for bodyweight work but needs positive whole reps", () => {
    expect(isSetCompletable({ weight: "0", reps: "10", rpe: "" })).toBe(true)
    expect(isSetCompletable({ weight: "60", reps: "0", rpe: "" })).toBe(false)
    expect(isSetCompletable({ weight: "60", reps: "7.5", rpe: "" })).toBe(false)
    expect(isSetCompletable({ weight: "", reps: "8", rpe: "" })).toBe(false)
    // The server rejects more than 100 reps, so the row must not offer to complete it.
    expect(isSetCompletable({ weight: "60", reps: "100", rpe: "" })).toBe(true)
    expect(isSetCompletable({ weight: "60", reps: "101", rpe: "" })).toBe(false)
  })

  it("treats a blank RPE as not provided and an out-of-range one as invalid", () => {
    expect(parseRpe("")).toBeNull()
    expect(parseRpe("8.5")).toBe(8.5)
    expect(parseRpe("11")).toBeUndefined()
    expect(parseRpe("abc")).toBeUndefined()
    expect(isSetCompletable({ weight: "60", reps: "8", rpe: "11" })).toBe(false)
  })
})

describe("sessionReducer", () => {
  it("changes a set's type", () => {
    const next = sessionReducer(started(), { type: "set-kind", exerciseId: "bench", setId: "bench-1", kind: "failure" })
    expect(next.exercises[0].sets.map((set) => set.kind)).toEqual(["warmup", "failure"])
  })

  it("ticking a valid set marks it done and starts the rest timer", () => {
    const next = sessionReducer(started(), { type: "toggle", exerciseId: "bench", setId: "bench-1", now: 1_000 })
    expect(next.exercises[0].sets[1].done).toBe(true)
    expect(next.rest).toEqual({ endsAt: 1_000 + 120_000, totalSeconds: 120 })
  })

  it("won't tick a set with missing values", () => {
    const blanked = sessionReducer(started(), { type: "edit", exerciseId: "bench", setId: "bench-1", field: "reps", value: "" })
    const next = sessionReducer(blanked, { type: "toggle", exerciseId: "bench", setId: "bench-1", now: 1_000 })
    expect(next.exercises[0].sets[1].done).toBe(false)
    expect(next.rest).toBeNull()
  })

  it("un-ticking a set leaves the rest timer alone", () => {
    const ticked = sessionReducer(started(), { type: "toggle", exerciseId: "bench", setId: "bench-1", now: 1_000 })
    const next = sessionReducer(ticked, { type: "toggle", exerciseId: "bench", setId: "bench-1", now: 2_000 })
    expect(next.exercises[0].sets[1].done).toBe(false)
    expect(next.rest).toEqual(ticked.rest)
  })

  it("adds a set copying the last one's numbers, but won't remove a completed last set", () => {
    const added = sessionReducer(started(), { type: "add-set", exerciseId: "bench" })
    expect(added.exercises[0].sets).toHaveLength(3)
    expect(added.exercises[0].sets[2]).toMatchObject({ kind: "working", weight: "60", reps: "8", done: false })

    const ticked = sessionReducer(added, { type: "toggle", exerciseId: "bench", setId: added.exercises[0].sets[2].id, now: 1 })
    expect(sessionReducer(ticked, { type: "remove-last-set", exerciseId: "bench" }).exercises[0].sets).toHaveLength(3)
    expect(sessionReducer(added, { type: "remove-last-set", exerciseId: "bench" }).exercises[0].sets).toHaveLength(2)
  })
})

describe("sessionTotals and toFinishInput", () => {
  function sessionWithMixedSets() {
    let state = started()
    state = sessionReducer(state, { type: "add-set", exerciseId: "bench" })
    state = sessionReducer(state, { type: "add-set", exerciseId: "bench" })
    const [warmup, working, extra1, extra2] = state.exercises[0].sets
    state = sessionReducer(state, { type: "set-kind", exerciseId: "bench", setId: extra1.id, kind: "failure" })
    state = sessionReducer(state, { type: "set-kind", exerciseId: "bench", setId: extra2.id, kind: "drop" })
    state = sessionReducer(state, { type: "edit", exerciseId: "bench", setId: extra2.id, field: "weight", value: "40" })
    state = sessionReducer(state, { type: "edit", exerciseId: "bench", setId: working.id, field: "rpe", value: "8" })
    for (const set of [warmup, working, extra1, extra2]) {
      state = sessionReducer(state, { type: "toggle", exerciseId: "bench", setId: set.id, now: 1 })
    }
    return state
  }

  it("counts every completed set except warm-ups toward volume", () => {
    // 60 x 8 (working) + 60 x 8 (failure) + 40 x 8 (drop); the 40 x 10 warm-up is excluded.
    expect(sessionTotals(sessionWithMixedSets().exercises)).toEqual({ done: 4, total: 4, volumeKg: 480 + 480 + 320 })
  })

  it("sends only completed sets, with their type and RPE", () => {
    const state = sessionReducer(sessionWithMixedSets(), { type: "add-set", exerciseId: "bench" })
    const input = toFinishInput(state, Date.UTC(2026, 9, 19, 10), Date.UTC(2026, 9, 19, 11))
    expect(input.planId).toBe("plan-1")
    expect(input.startedAt).toBe("2026-10-19T10:00:00.000Z")
    expect(input.exercises).toHaveLength(1)
    expect(input.exercises[0].sets.map((set) => [set.kind, set.weightKg, set.reps, set.rpe])).toEqual([
      ["warmup", 40, 10, undefined],
      ["working", 60, 8, 8],
      ["failure", 60, 8, undefined],
      ["drop", 40, 8, undefined],
    ])
  })

  it("leaves out an exercise with nothing completed", () => {
    expect(toFinishInput(started(), 0, 1).exercises).toEqual([])
  })
})
