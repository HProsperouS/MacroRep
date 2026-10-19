import { describe, expect, it } from "vitest"

import { isEditableSetValid, toEditable, toUpdateInput, type EditableWorkout } from "@/lib/workout-edit"
import type { WorkoutDetail } from "@/types/workout"

const detail: WorkoutDetail = {
  id: "w1",
  name: "Legs",
  startedAt: "2026-10-19T10:00:00Z",
  durationSeconds: 1800,
  exerciseCount: 1,
  setsCompleted: 2,
  volumeKg: 500,
  exercises: [
    {
      exerciseId: "squat",
      name: "Squat",
      sets: [
        { kind: "warmup", weightKg: 40, reps: 10, rpe: null },
        { kind: "working", weightKg: 100, reps: 5, rpe: 8.5 },
      ],
    },
  ],
}

describe("toEditable", () => {
  it("turns a logged workout into editable strings", () => {
    expect(toEditable(detail)).toEqual({
      name: "Legs",
      exercises: [
        {
          exerciseId: "squat",
          name: "Squat",
          sets: [
            { kind: "warmup", weight: "40", reps: "10", rpe: "" },
            { kind: "working", weight: "100", reps: "5", rpe: "8.5" },
          ],
        },
      ],
    })
  })

  it("refuses a workout whose exercise is no longer in the catalog", () => {
    expect(toEditable({ ...detail, exercises: [{ ...detail.exercises[0], exerciseId: null }] })).toBeNull()
  })
})

describe("toUpdateInput", () => {
  const editable = (): EditableWorkout => structuredClone(toEditable(detail)!)

  it("round-trips an unchanged workout", () => {
    expect(toUpdateInput(editable())).toEqual({
      name: "Legs",
      exercises: [
        {
          exerciseId: "squat",
          name: "Squat",
          sets: [
            { kind: "warmup", weightKg: 40, reps: 10, rpe: undefined },
            { kind: "working", weightKg: 100, reps: 5, rpe: 8.5 },
          ],
        },
      ],
    })
  })

  it("carries edits to type, weight, reps and RPE, and trims the name", () => {
    const workout = editable()
    workout.name = "  Leg day  "
    workout.exercises[0].sets[1] = { kind: "failure", weight: "102.5", reps: "6", rpe: "10" }
    const input = toUpdateInput(workout)
    expect(input?.name).toBe("Leg day")
    expect(input?.exercises[0].sets[1]).toEqual({ kind: "failure", weightKg: 102.5, reps: 6, rpe: 10 })
  })

  it("allows a failed zero-rep set", () => {
    const workout = editable()
    workout.exercises[0].sets[1].reps = "0"
    expect(toUpdateInput(workout)).not.toBeNull()
  })

  it.each([
    ["negative weight", { weight: "-5" }],
    ["blank weight", { weight: "" }],
    ["over the weight limit", { weight: "1001" }],
    ["fractional reps", { reps: "5.5" }],
    ["too many reps", { reps: "101" }],
    ["RPE above 10", { rpe: "11" }],
    ["RPE that isn't a number", { rpe: "hard" }],
  ])("is invalid with %s", (_label, change) => {
    const workout = editable()
    Object.assign(workout.exercises[0].sets[1], change)
    expect(isEditableSetValid(workout.exercises[0].sets[1])).toBe(false)
    expect(toUpdateInput(workout)).toBeNull()
  })

  it("is invalid with a blank name", () => {
    const workout = editable()
    workout.name = "   "
    expect(toUpdateInput(workout)).toBeNull()
  })

  it("drops an exercise whose sets were all removed, and is invalid once nothing is left", () => {
    const workout = editable()
    workout.exercises.push({ exerciseId: "bench", name: "Bench", sets: [{ kind: "working", weight: "60", reps: "8", rpe: "" }] })
    workout.exercises[0].sets = []
    expect(toUpdateInput(workout)?.exercises.map((exercise) => exercise.exerciseId)).toEqual(["bench"])

    workout.exercises[1].sets = []
    expect(toUpdateInput(workout)).toBeNull()
  })
})
