import { EQUIPMENT_LABELS, MUSCLE_LABELS, type Exercise, type FinishWorkoutInput, type PlannedExercise, type PlannedSet, type PlannedWorkout, type SetKind } from "@/types/workout"

/** Pure state for a live workout. Inputs are kept as strings so "57." can be typed. */

export type SessionSet = {
  id: string
  kind: SetKind
  weight: string
  reps: string
  previous?: PlannedSet["previous"]
  done: boolean
}

/** `id` is unique within the session (the same exercise can be added twice); `exerciseId` is the library id. */
export type SessionExercise = Omit<PlannedExercise, "sets"> & { exerciseId: string; sets: SessionSet[] }

export type RestTimer = { endsAt: number; totalSeconds: number }

export type SessionState = {
  name: string
  /** Null for an empty workout. */
  planId: string | null
  exercises: SessionExercise[]
  rest: RestTimer | null
  /** Counter for unique ids of added exercises and sets. */
  seq: number
}

export const EMPTY_WORKOUT_NAME = "Freestyle workout"
const DEFAULT_REST_SECONDS = 90
const DEFAULT_SET_COUNT = 3

export type SessionAction =
  | { type: "edit"; exerciseId: string; setId: string; field: "weight" | "reps"; value: string }
  | { type: "toggle"; exerciseId: string; setId: string; now: number }
  | { type: "add-set"; exerciseId: string }
  | { type: "adjust-rest"; seconds: number; now: number }
  | { type: "skip-rest" }
  | { type: "remove-last-set"; exerciseId: string }
  | { type: "add-exercises"; exercises: Exercise[] }
  | { type: "remove-exercise"; exerciseId: string }
  | { type: "restore-exercise"; exercise: SessionExercise; index: number }
  | { type: "move-exercise"; exerciseId: string; direction: -1 | 1 }

export function initSession(plan: PlannedWorkout | null): SessionState {
  if (!plan) return { name: EMPTY_WORKOUT_NAME, planId: null, exercises: [], rest: null, seq: 0 }
  return {
    name: plan.name,
    planId: plan.id,
    rest: null,
    seq: 0,
    exercises: plan.exercises.map(({ sets, ...exercise }) => ({
      ...exercise,
      exerciseId: exercise.id,
      sets: sets.map((set) => ({
        id: set.id,
        kind: set.kind,
        weight: set.targetWeightKg == null ? "" : String(set.targetWeightKg),
        reps: set.targetReps == null ? "" : String(set.targetReps),
        previous: set.previous,
        done: false,
      })),
    })),
  }
}

/** A library exercise becomes session rows pre-filled from its last session (or 3 blank sets). */
export function exerciseToSession(exercise: Exercise, instanceId: string): SessionExercise {
  const last = exercise.lastSession?.sets ?? []
  const count = Math.max(last.length, DEFAULT_SET_COUNT)
  return {
    id: instanceId,
    exerciseId: exercise.id,
    name: exercise.name,
    equipment: EQUIPMENT_LABELS[exercise.equipment],
    muscles: exercise.muscles.map((muscle) => MUSCLE_LABELS[muscle]).join(", "),
    restSeconds: DEFAULT_REST_SECONDS,
    sets: Array.from({ length: count }, (_, index) => {
      const previous = last[index] ?? last[last.length - 1]
      return {
        id: `${instanceId}-s${index + 1}`,
        kind: "working" as const,
        weight: previous ? String(previous.weightKg) : "",
        reps: previous ? String(previous.reps) : "",
        previous: last[index],
        done: false,
      }
    }),
  }
}

/** Weight may be 0 (bodyweight); reps must be a positive whole number. */
export function parseSet(set: Pick<SessionSet, "weight" | "reps">) {
  const weightKg = set.weight.trim() === "" ? Number.NaN : Number(set.weight)
  const reps = set.reps.trim() === "" ? Number.NaN : Number(set.reps)
  const valid = Number.isFinite(weightKg) && weightKg >= 0 && weightKg <= 1000 && Number.isInteger(reps) && reps > 0 && reps <= 200
  return valid ? { weightKg, reps } : null
}

function updateSet(state: SessionState, exerciseId: string, setId: string, update: (set: SessionSet, exercise: SessionExercise) => SessionSet) {
  return state.exercises.map((exercise) =>
    exercise.id === exerciseId ? { ...exercise, sets: exercise.sets.map((set) => (set.id === setId ? update(set, exercise) : set)) } : exercise,
  )
}

export function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "edit":
      return { ...state, exercises: updateSet(state, action.exerciseId, action.setId, (set) => ({ ...set, [action.field]: action.value })) }

    case "toggle": {
      const exercise = state.exercises.find((e) => e.id === action.exerciseId)
      const set = exercise?.sets.find((s) => s.id === action.setId)
      if (!exercise || !set) return state
      if (!set.done && !parseSet(set)) return state
      const exercises = updateSet(state, action.exerciseId, action.setId, (s) => ({ ...s, done: !s.done }))
      // Completing a set starts the rest timer; un-ticking leaves it alone.
      const rest = set.done ? state.rest : { endsAt: action.now + exercise.restSeconds * 1000, totalSeconds: exercise.restSeconds }
      return { ...state, exercises, rest }
    }

    case "add-set":
      return {
        ...state,
        seq: state.seq + 1,
        exercises: state.exercises.map((exercise) => {
          if (exercise.id !== action.exerciseId) return exercise
          const last = exercise.sets[exercise.sets.length - 1]
          const next: SessionSet = {
            id: `${exercise.id}-extra-${state.seq + 1}`,
            kind: "working",
            weight: last?.weight ?? "",
            reps: last?.reps ?? "",
            done: false,
          }
          return { ...exercise, sets: [...exercise.sets, next] }
        }),
      }

    case "adjust-rest": {
      if (!state.rest) return state
      const endsAt = Math.max(action.now, state.rest.endsAt + action.seconds * 1000)
      return { ...state, rest: { endsAt, totalSeconds: Math.max(state.rest.totalSeconds + action.seconds, 1) } }
    }

    case "skip-rest":
      return { ...state, rest: null }

    case "remove-last-set":
      return {
        ...state,
        exercises: state.exercises.map((exercise) => {
          const last = exercise.sets[exercise.sets.length - 1]
          if (exercise.id !== action.exerciseId || !last || last.done || exercise.sets.length <= 1) return exercise
          return { ...exercise, sets: exercise.sets.slice(0, -1) }
        }),
      }

    case "add-exercises": {
      const added = action.exercises.map((exercise, index) => exerciseToSession(exercise, `${exercise.id}-x${state.seq + index + 1}`))
      return { ...state, seq: state.seq + added.length, exercises: [...state.exercises, ...added] }
    }

    case "remove-exercise":
      return { ...state, exercises: state.exercises.filter((exercise) => exercise.id !== action.exerciseId) }

    case "restore-exercise": {
      if (state.exercises.some((exercise) => exercise.id === action.exercise.id)) return state
      const exercises = [...state.exercises]
      exercises.splice(Math.min(action.index, exercises.length), 0, action.exercise)
      return { ...state, exercises }
    }

    case "move-exercise": {
      const from = state.exercises.findIndex((exercise) => exercise.id === action.exerciseId)
      const to = from + action.direction
      if (from < 0 || to < 0 || to >= state.exercises.length) return state
      const exercises = [...state.exercises]
      const [moved] = exercises.splice(from, 1)
      exercises.splice(to, 0, moved)
      return { ...state, exercises }
    }
  }
}

/** Row labels: "W" for warm-ups, then 1, 2, 3… for working sets. */
export function setLabels(sets: Pick<SessionSet, "kind">[]) {
  const labels: string[] = []
  let working = 0
  for (const set of sets) {
    if (set.kind === "warmup") labels.push("W")
    else labels.push(String(++working))
  }
  return labels
}

export function sessionTotals(exercises: SessionExercise[]) {
  let done = 0
  let total = 0
  let volumeKg = 0
  for (const exercise of exercises) {
    for (const set of exercise.sets) {
      total += 1
      if (!set.done) continue
      done += 1
      const parsed = parseSet(set)
      if (parsed && set.kind === "working") volumeKg += parsed.weightKg * parsed.reps
    }
  }
  return { done, total, volumeKg }
}

export function toFinishInput(state: SessionState, startedAt: number, finishedAt: number): FinishWorkoutInput {
  return {
    planId: state.planId,
    name: state.name,
    startedAt: new Date(startedAt).toISOString(),
    finishedAt: new Date(finishedAt).toISOString(),
    exercises: state.exercises
      .map((exercise) => ({
        exerciseId: exercise.exerciseId,
        name: exercise.name,
        sets: exercise.sets.flatMap((set) => {
          const parsed = set.done ? parseSet(set) : null
          return parsed ? [{ kind: set.kind, ...parsed }] : []
        }),
      }))
      .filter((exercise) => exercise.sets.length > 0),
  }
}
