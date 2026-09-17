import type { PlannedExercise, PlannedSet, PlannedWorkout, PreviousSet } from "@/types/workout"

/** Sample plan used by the mock API. Matches the design canvas (Week 4 · Day 2). */

function sets(exerciseId: string, spec: { kind?: PlannedSet["kind"]; kg: number | null; reps: number; prev?: PreviousSet }[]): PlannedSet[] {
  return spec.map((s, index) => ({
    id: `${exerciseId}-s${index + 1}`,
    kind: s.kind ?? "working",
    targetWeightKg: s.kg,
    targetReps: s.reps,
    previous: s.prev,
  }))
}

const EXERCISES: PlannedExercise[] = [
  {
    id: "bench",
    name: "Bench press",
    equipment: "Barbell",
    muscles: "Chest, triceps",
    restSeconds: 120,
    tag: "PR pace",
    note: "Last time: 57.5 kg × 8, 8, 7. Try +2.5 kg.",
    sets: sets("bench", [
      { kind: "warmup", kg: 40, reps: 10, prev: { weightKg: 40, reps: 10 } },
      { kg: 60, reps: 8, prev: { weightKg: 57.5, reps: 8 } },
      { kg: 60, reps: 8, prev: { weightKg: 57.5, reps: 8 } },
      { kg: 60, reps: 8, prev: { weightKg: 57.5, reps: 7 } },
    ]),
  },
  {
    id: "cable-row",
    name: "Seated cable row",
    equipment: "Cable",
    muscles: "Back, biceps",
    restSeconds: 90,
    sets: sets("cable-row", [
      { kg: 52.5, reps: 10, prev: { weightKg: 50, reps: 10 } },
      { kg: 52.5, reps: 10, prev: { weightKg: 50, reps: 10 } },
      { kg: 52.5, reps: 10, prev: { weightKg: 50, reps: 9 } },
    ]),
  },
  {
    id: "ohp",
    name: "Overhead press",
    equipment: "Barbell",
    muscles: "Shoulders, triceps",
    restSeconds: 120,
    sets: sets("ohp", [
      { kg: 37.5, reps: 8, prev: { weightKg: 37.5, reps: 7 } },
      { kg: 37.5, reps: 8, prev: { weightKg: 37.5, reps: 7 } },
      { kg: 37.5, reps: 8, prev: { weightKg: 35, reps: 8 } },
    ]),
  },
  {
    id: "lat-pulldown",
    name: "Lat pulldown",
    equipment: "Cable",
    muscles: "Back, biceps",
    restSeconds: 90,
    sets: sets("lat-pulldown", [
      { kg: 55, reps: 10, prev: { weightKg: 55, reps: 10 } },
      { kg: 55, reps: 10, prev: { weightKg: 55, reps: 9 } },
      { kg: 55, reps: 10, prev: { weightKg: 52.5, reps: 10 } },
    ]),
  },
  {
    id: "lateral-raise",
    name: "Lateral raise",
    equipment: "Dumbbell",
    muscles: "Side delts",
    restSeconds: 60,
    sets: sets("lateral-raise", [
      { kg: 8, reps: 15, prev: { weightKg: 8, reps: 14 } },
      { kg: 8, reps: 15, prev: { weightKg: 8, reps: 13 } },
      { kg: 8, reps: 15, prev: { weightKg: 8, reps: 12 } },
    ]),
  },
  {
    id: "triceps-pushdown",
    name: "Triceps pushdown",
    equipment: "Cable",
    muscles: "Triceps",
    restSeconds: 60,
    sets: sets("triceps-pushdown", [
      { kg: 25, reps: 12, prev: { weightKg: 25, reps: 12 } },
      { kg: 25, reps: 12, prev: { weightKg: 22.5, reps: 12 } },
    ]),
  },
]

export const SAMPLE_WORKOUT: PlannedWorkout = {
  id: "plan-w4-d2",
  name: "Upper A — Push focus",
  weekLabel: "Week 4 · Day 2",
  estimatedMinutes: 55,
  exercises: EXERCISES,
  highlight: {
    exercise: "Bench press",
    estimated1RmKg: 76,
    changeKg: 4,
    periodLabel: "8 wk",
    bestSet: "60 kg × 8",
  },
}
