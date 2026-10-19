import { parseRpe } from "@/lib/workout-session"
import type { SetKind, UpdateWorkoutInput, WorkoutDetail } from "@/types/workout"

/** A logged workout being corrected. Inputs stay strings so "57." can be typed. */

export type EditableSet = { kind: SetKind; weight: string; reps: string; rpe: string }
export type EditableExercise = { exerciseId: string; name: string; sets: EditableSet[] }
export type EditableWorkout = { name: string; exercises: EditableExercise[] }

const MAX_NAME_LENGTH = 255
const MAX_WEIGHT_KG = 1000
const MAX_REPS = 100

/** Null when an exercise was removed from the catalog after it was logged: such a workout can only be deleted. */
export function toEditable(detail: WorkoutDetail): EditableWorkout | null {
  const exercises: EditableExercise[] = []
  for (const exercise of detail.exercises) {
    if (exercise.exerciseId === null) return null
    exercises.push({
      exerciseId: exercise.exerciseId,
      name: exercise.name,
      sets: exercise.sets.map((set) => ({
        kind: set.kind,
        weight: String(set.weightKg),
        reps: String(set.reps),
        rpe: set.rpe == null ? "" : String(set.rpe),
      })),
    })
  }
  return { name: detail.name, exercises }
}

/** Reps may be 0 here (a failed attempt is still a logged set), unlike a set being completed live. */
function parseEditableSet(set: EditableSet) {
  const weightKg = set.weight.trim() === "" ? Number.NaN : Number(set.weight)
  const reps = set.reps.trim() === "" ? Number.NaN : Number(set.reps)
  const rpe = parseRpe(set.rpe)
  const valid =
    Number.isFinite(weightKg) &&
    weightKg >= 0 &&
    weightKg <= MAX_WEIGHT_KG &&
    Number.isInteger(reps) &&
    reps >= 0 &&
    reps <= MAX_REPS &&
    rpe !== undefined
  return valid ? { kind: set.kind, weightKg, reps, rpe } : null
}

export function isEditableSetValid(set: EditableSet) {
  return parseEditableSet(set) !== null
}

export function isWorkoutNameValid(name: string) {
  return name.trim().length > 0 && name.trim().length <= MAX_NAME_LENGTH
}

/** The request to save, or null while anything is invalid or no set is left. Exercises emptied of sets are dropped. */
export function toUpdateInput(workout: EditableWorkout): UpdateWorkoutInput | null {
  if (!isWorkoutNameValid(workout.name)) return null
  const exercises: UpdateWorkoutInput["exercises"] = []
  for (const exercise of workout.exercises) {
    const sets = []
    for (const set of exercise.sets) {
      const parsed = parseEditableSet(set)
      if (!parsed) return null
      sets.push({ kind: parsed.kind, weightKg: parsed.weightKg, reps: parsed.reps, rpe: parsed.rpe ?? undefined })
    }
    if (sets.length > 0) exercises.push({ exerciseId: exercise.exerciseId, name: exercise.name, sets })
  }
  return exercises.length > 0 ? { name: workout.name.trim(), exercises } : null
}
