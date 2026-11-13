import { adviseWeight } from "@/lib/find-weight"
import { EQUIPMENT_LABELS, MUSCLE_LABELS, SET_KIND_LABELS, type Exercise, type FinishWorkoutInput, type PlannedExercise, type PlannedSet, type PlannedWorkout, type SetKind } from "@/types/workout"

/** Pure state for a live workout. Inputs are kept as strings so "57." can be typed. */

export type SessionSet = {
  id: string
  kind: SetKind
  weight: string
  reps: string
  /** Rating of Perceived Exertion, kept as a string like weight/reps; optional so it may be blank. */
  rpe: string
  previous?: PlannedSet["previous"]
  done: boolean
}

/** `id` is unique within the session (the same exercise can be added twice); `exerciseId` is the library id.
 *  `finding` marks an exercise with no history and no target weight, where the lifter finds their
 *  weight by feel (see lib/find-weight.ts). Absent on workouts saved before it existed. */
export type SessionExercise = Omit<PlannedExercise, "sets" | "userNote"> & {
  exerciseId: string
  sets: SessionSet[]
  finding?: boolean
  /** The lifter's own note on this exercise, saved to the server as they edit it. Absent on
   *  workouts saved before notes existed. */
  userNote?: string
}

export type RestTimer = { endsAt: number; totalSeconds: number }

export type SessionState = {
  name: string
  /** Null for an empty workout. */
  planId: string | null
  exercises: SessionExercise[]
  /** Started by hand, so each rest can be as long as that set needs. */
  rest: RestTimer | null
  /** The exercise of the set ticked most recently, whose rest time the timer suggests. */
  lastCompletedExerciseId?: string | null
  /** Counter for unique ids of added exercises and sets. */
  seq: number
}

const EMPTY_WORKOUT_NAME = "Freestyle workout"
export const DEFAULT_REST_SECONDS = 90
export const MIN_REST_SECONDS = 5
export const MAX_REST_SECONDS = 600
const DEFAULT_SET_COUNT = 3

export type SessionAction =
  | { type: "edit"; exerciseId: string; setId: string; field: "weight" | "reps" | "rpe"; value: string }
  | { type: "set-kind"; exerciseId: string; setId: string; kind: SetKind }
  | { type: "toggle"; exerciseId: string; setId: string; now: number }
  | { type: "add-set"; exerciseId: string }
  | { type: "edit-note"; exerciseId: string; value: string }
  | { type: "start-rest"; seconds: number; now: number }
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
    exercises: plan.exercises.map(({ sets, userNote, ...exercise }) => ({
      ...exercise,
      exerciseId: exercise.id,
      userNote: userNote ?? "",
      finding: isFirstTime(sets),
      sets: sets.map((set) => ({
        id: set.id,
        kind: set.kind,
        weight: set.targetWeightKg == null ? "" : String(set.targetWeightKg),
        reps: set.targetReps == null ? "" : String(set.targetReps),
        rpe: "",
        previous: set.previous,
        done: false,
      })),
    })),
  }
}

/** No past session and no target weight for any working set: nothing to say what to lift. */
function isFirstTime(sets: PlannedSet[]) {
  const working = sets.filter((set) => set.kind !== "warmup")
  return working.length > 0 && working.every((set) => set.previous == null && (set.targetWeightKg ?? 0) <= 0)
}

/** A library exercise becomes session rows pre-filled from its last session (or 3 blank sets). */
function exerciseToSession(exercise: Exercise, instanceId: string): SessionExercise {
  const last = exercise.lastSession?.sets ?? []
  const count = Math.max(last.length, DEFAULT_SET_COUNT)
  return {
    id: instanceId,
    exerciseId: exercise.id,
    name: exercise.name,
    equipment: EQUIPMENT_LABELS[exercise.equipment],
    muscles: exercise.muscles.map((muscle) => MUSCLE_LABELS[muscle]).join(", "),
    restSeconds: DEFAULT_REST_SECONDS,
    userNote: exercise.userNote ?? "",
    finding: last.length === 0,
    sets: Array.from({ length: count }, (_, index) => {
      const previous = last[index] ?? last[last.length - 1]
      return {
        id: `${instanceId}-s${index + 1}`,
        kind: "working" as const,
        weight: previous ? String(previous.weightKg) : "",
        reps: previous ? String(previous.reps) : "",
        rpe: "",
        previous: last[index],
        done: false,
      }
    }),
  }
}

/** Weight may be 0 (bodyweight); reps must be a positive whole number. */
function parseSet(set: Pick<SessionSet, "weight" | "reps">) {
  const weightKg = set.weight.trim() === "" ? Number.NaN : Number(set.weight)
  const reps = set.reps.trim() === "" ? Number.NaN : Number(set.reps)
  const valid = Number.isFinite(weightKg) && weightKg >= 0 && weightKg <= 1000 && Number.isInteger(reps) && reps > 0 && reps <= 100
  return valid ? { weightKg, reps } : null
}

/** RPE is optional: blank parses to `null` (not provided, not invalid); anything but 1–10 in
 *  half steps (as the server accepts) parses to `undefined` (invalid). */
export function parseRpe(rpe: string): number | null | undefined {
  if (rpe.trim() === "") return null
  const value = Number(rpe)
  return Number.isFinite(value) && value >= 1 && value <= 10 && Number.isInteger(value * 2) ? value : undefined
}

/** The single definition of "can this set be marked done" — an out-of-range RPE must
 * block completion too, or toFinishInput silently drops it on save. Shared by the
 * "toggle" reducer case and the row's disabled state so they can't drift apart. */
export function isSetCompletable(set: Pick<SessionSet, "weight" | "reps" | "rpe">) {
  return parseSet(set) !== null && parseRpe(set.rpe) !== undefined
}

/** While finding a weight, a completed working set with an RPE sets the next one's weight, unless the
 *  lifter already chose a different weight for it. */
function fillNextWeight(exercises: SessionExercise[], exerciseId: string, completed: SessionSet) {
  const rpe = parseRpe(completed.rpe)
  const advice = completed.kind === "working" && rpe != null ? adviseWeight(Number(completed.weight), rpe) : null
  if (!advice) return exercises
  return exercises.map((exercise) => {
    if (exercise.id !== exerciseId) return exercise
    const index = exercise.sets.findIndex((s) => s.kind === "working" && !s.done && s.id !== completed.id)
    const next = exercise.sets[index]
    if (!next || (next.weight.trim() !== "" && Number(next.weight) !== Number(completed.weight))) return exercise
    return { ...exercise, sets: exercise.sets.map((s, i) => (i === index ? { ...s, weight: String(advice.weightKg) } : s)) }
  })
}

export function clampRest(seconds: number) {
  return Math.min(MAX_REST_SECONDS, Math.max(MIN_REST_SECONDS, Math.round(seconds)))
}

/** The rest the timer suggests: the most recently ticked exercise's, else the first exercise's. */
export function suggestedRestSeconds(state: Pick<SessionState, "exercises" | "lastCompletedExerciseId">) {
  const exercise = state.exercises.find((e) => e.id === state.lastCompletedExerciseId) ?? state.exercises[0]
  return exercise?.restSeconds || DEFAULT_REST_SECONDS
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

    case "set-kind":
      return { ...state, exercises: updateSet(state, action.exerciseId, action.setId, (set) => ({ ...set, kind: action.kind })) }

    case "toggle": {
      const exercise = state.exercises.find((e) => e.id === action.exerciseId)
      const set = exercise?.sets.find((s) => s.id === action.setId)
      if (!exercise || !set) return state
      if (!set.done && !isSetCompletable(set)) return state
      let exercises = updateSet(state, action.exerciseId, action.setId, (s) => ({ ...s, done: !s.done }))
      if (!set.done && exercise.finding) exercises = fillNextWeight(exercises, exercise.id, set)
      // The rest timer is started by hand (each set may want a different rest); completing a set
      // only marks which exercise's rest time to suggest.
      return { ...state, exercises, lastCompletedExerciseId: set.done ? state.lastCompletedExerciseId : exercise.id }
    }

    case "edit-note":
      // Every instance of the same library exercise shares one note.
      return {
        ...state,
        exercises: state.exercises.map((exercise) => (exercise.exerciseId === action.exerciseId ? { ...exercise, userNote: action.value } : exercise)),
      }

    case "start-rest": {
      const seconds = clampRest(action.seconds)
      return { ...state, rest: { endsAt: action.now + seconds * 1000, totalSeconds: seconds } }
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
            rpe: "",
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

const SET_KIND_LETTERS: Partial<Record<SetKind, string>> = { warmup: "W", failure: "F", drop: "D" }

/** Row labels: a letter for warm-up, failure and drop sets, and 1, 2, 3… for working sets. */
export function setLabels(sets: Pick<SessionSet, "kind">[]) {
  const labels: string[] = []
  let working = 0
  for (const set of sets) labels.push(SET_KIND_LETTERS[set.kind] ?? String(++working))
  return labels
}

/** Labels for a finished exercise's sets: "Warm-up", "Set 1", "Set 2", "Failure", "Drop set". */
export function historySetLabels(sets: Pick<SessionSet, "kind">[]) {
  const letters = setLabels(sets)
  return sets.map((set, index) => (set.kind === "working" ? `Set ${letters[index]}` : SET_KIND_LABELS[set.kind]))
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
      if (parsed && set.kind !== "warmup") volumeKg += parsed.weightKg * parsed.reps
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
          if (!parsed) return []
          const rpe = parseRpe(set.rpe)
          return [{ kind: set.kind, ...parsed, rpe: rpe ?? undefined }]
        }),
      }))
      .filter((exercise) => exercise.sets.length > 0),
  }
}
