import { formatNumber, toNumber } from "@/lib/format"
import type { Exercise, PlannedWorkout, SaveRoutineInput, SetKind } from "@/types/workout"

/** Pure state for the routine editor. Inputs are kept as strings so "57." can be typed. */

export type DraftSet = { id: string; kind: SetKind; targetWeightKg: string; targetReps: string }

/** `instanceId` is unique within the routine (the same exercise can be added twice). */
export type DraftExercise = { instanceId: string; exerciseId: string; name: string; restSeconds: string; sets: DraftSet[] }

export type RoutineDraft = {
  name: string
  exercises: DraftExercise[]
  /** Counter for unique ids of added exercises and sets. */
  seq: number
}

export type DraftAction =
  | { type: "rename"; name: string }
  | { type: "add-exercises"; exercises: Exercise[] }
  | { type: "move"; instanceId: string; direction: -1 | 1 }
  | { type: "remove"; instanceId: string }
  | { type: "set-rest"; instanceId: string; value: string }
  | { type: "add-set"; instanceId: string }
  | { type: "remove-set"; instanceId: string; setId: string }
  | { type: "edit-set"; instanceId: string; setId: string; patch: Partial<Omit<DraftSet, "id">> }

const DEFAULT_REST_SECONDS = 90

/** What the server accepts for a routine; blank fields take a default (rest) or mean no target. */
export const ROUTINE_LIMITS = {
  rest: { min: 0, max: 600, whole: true },
  weight: { min: 0, max: 1_000, whole: false },
  reps: { min: 1, max: 100, whole: true },
} as const

export function rangeError(raw: string, { min, max, whole }: { min: number; max: number; whole: boolean }) {
  if (raw.trim() === "") return undefined
  const value = toNumber(raw)
  if (value === undefined) return "Enter a number"
  if (whole && !Number.isInteger(value)) return "Whole number"
  if (value < min || value > max) return `${formatNumber(min)}–${formatNumber(max)}`
  return undefined
}

export function draftFromRoutine(plan: PlannedWorkout | null): RoutineDraft {
  if (!plan) return { name: "New routine", exercises: [], seq: 0 }
  return {
    name: plan.name,
    exercises: plan.exercises.map((exercise, index) => ({
      instanceId: `${exercise.id}-${index}`,
      exerciseId: exercise.id,
      name: exercise.name,
      restSeconds: String(exercise.restSeconds),
      sets: exercise.sets.map((set) => ({
        id: set.id,
        kind: set.kind,
        targetWeightKg: set.targetWeightKg == null ? "" : String(set.targetWeightKg),
        targetReps: set.targetReps == null ? "" : String(set.targetReps),
      })),
    })),
    seq: 0,
  }
}

function newSet(kind: SetKind, id: string): DraftSet {
  return { id, kind, targetWeightKg: "", targetReps: "" }
}

function updateExercise(draft: RoutineDraft, instanceId: string, update: (exercise: DraftExercise) => DraftExercise): RoutineDraft {
  return { ...draft, exercises: draft.exercises.map((exercise) => (exercise.instanceId === instanceId ? update(exercise) : exercise)) }
}

export function routineDraftReducer(draft: RoutineDraft, action: DraftAction): RoutineDraft {
  switch (action.type) {
    case "rename":
      return { ...draft, name: action.name }
    case "add-exercises": {
      let seq = draft.seq
      const added = action.exercises.map((exercise) => {
        seq += 1
        const instanceId = `${exercise.id}-new-${seq}`
        return {
          instanceId,
          exerciseId: exercise.id,
          name: exercise.name,
          restSeconds: String(DEFAULT_REST_SECONDS),
          sets: [newSet("warmup", `${instanceId}-w1`), newSet("working", `${instanceId}-s1`), newSet("working", `${instanceId}-s2`)],
        }
      })
      return { ...draft, exercises: [...draft.exercises, ...added], seq }
    }
    case "move": {
      const from = draft.exercises.findIndex((exercise) => exercise.instanceId === action.instanceId)
      const to = from + action.direction
      if (from < 0 || to < 0 || to >= draft.exercises.length) return draft
      const exercises = [...draft.exercises]
      const [moved] = exercises.splice(from, 1)
      exercises.splice(to, 0, moved)
      return { ...draft, exercises }
    }
    case "remove":
      return { ...draft, exercises: draft.exercises.filter((exercise) => exercise.instanceId !== action.instanceId) }
    case "set-rest":
      return updateExercise(draft, action.instanceId, (exercise) => ({ ...exercise, restSeconds: action.value }))
    case "add-set": {
      const seq = draft.seq + 1
      const next = updateExercise(draft, action.instanceId, (exercise) => ({
        ...exercise,
        sets: [...exercise.sets, newSet("working", `${exercise.instanceId}-extra-${seq}`)],
      }))
      return { ...next, seq }
    }
    case "remove-set":
      // An exercise keeps at least one set.
      return updateExercise(draft, action.instanceId, (exercise) =>
        exercise.sets.length > 1 ? { ...exercise, sets: exercise.sets.filter((set) => set.id !== action.setId) } : exercise,
      )
    case "edit-set":
      return updateExercise(draft, action.instanceId, (exercise) => ({
        ...exercise,
        sets: exercise.sets.map((set) => (set.id === action.setId ? { ...set, ...action.patch } : set)),
      }))
  }
}

/** Whether the draft can be saved: a name (it's how the routine is picked in the week schedule),
 * at least one exercise, each with a set, and every value within the limits. */
export function canSaveDraft(draft: RoutineDraft) {
  const outOfRange = draft.exercises.some(
    (exercise) =>
      rangeError(exercise.restSeconds, ROUTINE_LIMITS.rest) !== undefined ||
      exercise.sets.some((set) => rangeError(set.targetWeightKg, ROUTINE_LIMITS.weight) !== undefined || rangeError(set.targetReps, ROUTINE_LIMITS.reps) !== undefined),
  )
  return draft.name.trim() !== "" && !outOfRange && draft.exercises.length > 0 && draft.exercises.every((exercise) => exercise.sets.length > 0)
}

export function toSaveRoutineInput(draft: RoutineDraft): SaveRoutineInput {
  return {
    name: draft.name.trim(),
    exercises: draft.exercises.map((exercise) => ({
      exerciseId: exercise.exerciseId,
      restSeconds: toNumber(exercise.restSeconds) ?? DEFAULT_REST_SECONDS,
      sets: exercise.sets.map((set) => ({
        kind: set.kind,
        targetWeightKg: toNumber(set.targetWeightKg) ?? null,
        targetReps: toNumber(set.targetReps) ?? null,
      })),
    })),
  }
}
