export const EQUIPMENT = ["barbell", "dumbbell", "cable", "machine", "bodyweight", "kettlebell", "band"] as const
export type Equipment = (typeof EQUIPMENT)[number]

export const EQUIPMENT_LABELS: Record<Equipment, string> = {
  barbell: "Barbell",
  dumbbell: "Dumbbell",
  cable: "Cable",
  machine: "Machine",
  bodyweight: "Bodyweight",
  kettlebell: "Kettlebell",
  band: "Band",
}

export const MUSCLE_GROUPS = ["chest", "back", "shoulders", "biceps", "triceps", "quads", "hamstrings", "glutes", "calves", "core"] as const
export type MuscleGroup = (typeof MUSCLE_GROUPS)[number]

export const MUSCLE_LABELS: Record<MuscleGroup, string> = {
  chest: "Chest",
  back: "Back",
  shoulders: "Shoulders",
  biceps: "Biceps",
  triceps: "Triceps",
  quads: "Quads",
  hamstrings: "Hamstrings",
  glutes: "Glutes",
  calves: "Calves",
  core: "Core",
}

export type SetKind = "warmup" | "working"

export type PreviousSet = {
  weightKg: number
  reps: number
}

/** One planned set. Target values pre-fill the logger. */
export type PlannedSet = {
  id: string
  kind: SetKind
  targetWeightKg: number | null
  targetReps: number | null
  previous?: PreviousSet
}

/** An exercise from the library, or one the user created (private to them). */
export type Exercise = {
  id: string
  name: string
  equipment: Equipment
  muscles: MuscleGroup[]
  source: "library" | "custom"
  /** Most recent logged session of this exercise, used for "Previous" and pre-filled sets. */
  lastSession?: { date: string; sets: PreviousSet[] }
}

export type ExerciseFilters = {
  q: string
  muscle?: MuscleGroup
  equipment?: Equipment
}

export type CreateExerciseInput = Pick<Exercise, "name" | "equipment" | "muscles">

export type PlannedExercise = {
  /** Library exercise id. */
  id: string
  name: string
  equipment: string
  muscles: string
  restSeconds: number
  /** Progression hint from the last session, e.g. "Last time: 57.5 kg × 8, 8, 7. Try +2.5 kg." */
  note?: string
  /** Shown as a badge, e.g. "PR pace". */
  tag?: string
  sets: PlannedSet[]
}

export type StrengthHighlight = {
  exercise: string
  estimated1RmKg: number
  changeKg: number
  periodLabel: string
  bestSet: string
}

export type PlannedWorkout = {
  id: string
  name: string
  weekLabel: string
  estimatedMinutes: number
  exercises: PlannedExercise[]
  highlight?: StrengthHighlight
}

export type LoggedSet = {
  kind: SetKind
  weightKg: number
  reps: number
}

export type FinishWorkoutInput = {
  /** Null for an empty (freestyle) workout. */
  planId: string | null
  name: string
  startedAt: string
  finishedAt: string
  exercises: { exerciseId: string; name: string; sets: LoggedSet[] }[]
}

export type WorkoutSummary = {
  id: string
  name: string
  durationSeconds: number
  setsCompleted: number
  volumeKg: number
  personalRecords: string[]
}
