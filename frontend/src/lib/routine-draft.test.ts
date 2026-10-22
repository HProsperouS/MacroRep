import { describe, expect, it } from "vitest"

import { canSaveDraft, draftFromRoutine, rangeError, ROUTINE_LIMITS, routineDraftReducer, toSaveRoutineInput, type DraftAction, type RoutineDraft } from "@/lib/routine-draft"
import type { Exercise, PlannedWorkout } from "@/types/workout"

const routine: PlannedWorkout = {
  id: "routine-1",
  name: "Push day",
  estimatedMinutes: 20,
  exercises: [
    {
      id: "bench",
      name: "Bench Press",
      equipment: "Barbell",
      muscles: "Chest",
      restSeconds: 120,
      sets: [
        { id: "bench-0", kind: "warmup", targetWeightKg: 40, targetReps: 10 },
        { id: "bench-1", kind: "working", targetWeightKg: null, targetReps: 8 },
      ],
    },
  ],
}

const squat: Exercise = { id: "squat", name: "Squat", equipment: "barbell", muscles: ["quads"], source: "library" }

function apply(draft: RoutineDraft, ...actions: DraftAction[]) {
  return actions.reduce(routineDraftReducer, draft)
}

describe("draftFromRoutine", () => {
  it("starts a new routine empty", () => {
    expect(draftFromRoutine(null)).toEqual({ name: "New routine", exercises: [], seq: 0 })
  })

  it("keeps the routine's values as text, a missing target as blank", () => {
    const [bench] = draftFromRoutine(routine).exercises
    expect(bench.restSeconds).toBe("120")
    expect(bench.sets.map((set) => [set.targetWeightKg, set.targetReps])).toEqual([
      ["40", "10"],
      ["", "8"],
    ])
  })
})

describe("routineDraftReducer", () => {
  it("adds an exercise with a warm-up and two working sets, each id unique", () => {
    const draft = apply(draftFromRoutine(routine), { type: "add-exercises", exercises: [squat, squat] })
    const added = draft.exercises.slice(1)
    expect(added.map((exercise) => exercise.sets.map((set) => set.kind))).toEqual([
      ["warmup", "working", "working"],
      ["warmup", "working", "working"],
    ])
    const instanceIds = draft.exercises.map((exercise) => exercise.instanceId)
    const setIds = draft.exercises.flatMap((exercise) => exercise.sets.map((set) => set.id))
    expect(new Set(instanceIds).size).toBe(instanceIds.length)
    expect(new Set(setIds).size).toBe(setIds.length)
  })

  it("moves an exercise, and leaves the ends where they are", () => {
    const draft = apply(draftFromRoutine(routine), { type: "add-exercises", exercises: [squat] })
    const [bench, added] = draft.exercises
    expect(apply(draft, { type: "move", instanceId: added.instanceId, direction: -1 }).exercises).toEqual([added, bench])
    expect(apply(draft, { type: "move", instanceId: bench.instanceId, direction: -1 })).toBe(draft)
  })

  it("adds and removes sets, but keeps at least one", () => {
    const draft = draftFromRoutine(routine)
    const { instanceId } = draft.exercises[0]
    const added = apply(draft, { type: "add-set", instanceId })
    expect(added.exercises[0].sets).toHaveLength(3)

    const one = apply(draft, { type: "remove-set", instanceId, setId: "bench-0" })
    expect(one.exercises[0].sets.map((set) => set.id)).toEqual(["bench-1"])
    expect(apply(one, { type: "remove-set", instanceId, setId: "bench-1" }).exercises[0].sets).toHaveLength(1)
  })

  it("edits a set and the rest", () => {
    const draft = draftFromRoutine(routine)
    const { instanceId } = draft.exercises[0]
    const edited = apply(
      draft,
      { type: "edit-set", instanceId, setId: "bench-1", patch: { targetWeightKg: "62.5", kind: "warmup" } },
      { type: "set-rest", instanceId, value: "90" },
    )
    expect(edited.exercises[0].restSeconds).toBe("90")
    expect(edited.exercises[0].sets[1]).toMatchObject({ kind: "warmup", targetWeightKg: "62.5", targetReps: "8" })
  })
})

describe("saving", () => {
  it("needs a name, an exercise, and values within the limits", () => {
    const draft = draftFromRoutine(routine)
    const { instanceId } = draft.exercises[0]
    expect(canSaveDraft(draft)).toBe(true)
    expect(canSaveDraft(apply(draft, { type: "rename", name: "  " }))).toBe(false)
    expect(canSaveDraft(apply(draft, { type: "remove", instanceId }))).toBe(false)
    expect(canSaveDraft(apply(draft, { type: "edit-set", instanceId, setId: "bench-1", patch: { targetReps: "0" } }))).toBe(false)
  })

  it("sends numbers, a blank target as null and a blank rest as the default", () => {
    const draft = apply(draftFromRoutine(routine), { type: "rename", name: " Push " }, { type: "set-rest", instanceId: "bench-0", value: "" })
    expect(toSaveRoutineInput(draft)).toEqual({
      name: "Push",
      exercises: [
        {
          exerciseId: "bench",
          restSeconds: 90,
          sets: [
            { kind: "warmup", targetWeightKg: 40, targetReps: 10 },
            { kind: "working", targetWeightKg: null, targetReps: 8 },
          ],
        },
      ],
    })
  })

  it("explains a value out of range", () => {
    expect(rangeError("", ROUTINE_LIMITS.reps)).toBeUndefined()
    expect(rangeError("abc", ROUTINE_LIMITS.reps)).toBe("Enter a number")
    expect(rangeError("8.5", ROUTINE_LIMITS.reps)).toBe("Whole number")
    expect(rangeError("101", ROUTINE_LIMITS.reps)).toBe("1–100")
  })
})
