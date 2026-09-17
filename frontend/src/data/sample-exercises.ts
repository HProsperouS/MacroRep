import { format, subDays } from "date-fns"

import type { Exercise, PreviousSet } from "@/types/workout"

/** Sample exercise library for the mock API. Ids match the plan in sample-workout.ts. */

const day = (daysAgo: number) => format(subDays(new Date(), daysAgo), "yyyy-MM-dd")
const reps = (weightKg: number, ...counts: number[]): PreviousSet[] => counts.map((r) => ({ weightKg, reps: r }))

export const SAMPLE_EXERCISES: Exercise[] = [
  { id: "bench", name: "Bench press", equipment: "barbell", muscles: ["chest", "triceps"], source: "library", lastSession: { date: day(2), sets: reps(57.5, 8, 8, 7) } },
  { id: "incline-db-press", name: "Incline dumbbell press", equipment: "dumbbell", muscles: ["chest", "shoulders"], source: "library", lastSession: { date: day(5), sets: reps(22, 10, 9, 8) } },
  { id: "chest-fly", name: "Cable chest fly", equipment: "cable", muscles: ["chest"], source: "library" },
  { id: "push-up", name: "Push-up", equipment: "bodyweight", muscles: ["chest", "triceps"], source: "library" },
  { id: "ohp", name: "Overhead press", equipment: "barbell", muscles: ["shoulders", "triceps"], source: "library", lastSession: { date: day(2), sets: reps(37.5, 7, 7, 8) } },
  { id: "lateral-raise", name: "Lateral raise", equipment: "dumbbell", muscles: ["shoulders"], source: "library", lastSession: { date: day(2), sets: reps(8, 14, 13, 12) } },
  { id: "face-pull", name: "Face pull", equipment: "cable", muscles: ["shoulders", "back"], source: "library" },
  { id: "cable-row", name: "Seated cable row", equipment: "cable", muscles: ["back", "biceps"], source: "library", lastSession: { date: day(2), sets: reps(50, 10, 10, 9) } },
  { id: "lat-pulldown", name: "Lat pulldown", equipment: "cable", muscles: ["back", "biceps"], source: "library", lastSession: { date: day(2), sets: reps(55, 10, 9, 10) } },
  { id: "pull-up", name: "Pull-up", equipment: "bodyweight", muscles: ["back", "biceps"], source: "library", lastSession: { date: day(4), sets: reps(0, 8, 7, 6) } },
  { id: "barbell-row", name: "Barbell row", equipment: "barbell", muscles: ["back"], source: "library", lastSession: { date: day(4), sets: reps(60, 8, 8, 8) } },
  { id: "deadlift", name: "Deadlift", equipment: "barbell", muscles: ["hamstrings", "glutes", "back"], source: "library", lastSession: { date: day(4), sets: reps(115, 5, 5, 5) } },
  { id: "back-squat", name: "Back squat", equipment: "barbell", muscles: ["quads", "glutes"], source: "library", lastSession: { date: day(4), sets: reps(90, 6, 6, 6) } },
  { id: "front-squat", name: "Front squat", equipment: "barbell", muscles: ["quads", "core"], source: "library" },
  { id: "leg-press", name: "Leg press", equipment: "machine", muscles: ["quads", "glutes"], source: "library", lastSession: { date: day(4), sets: reps(160, 12, 12, 10) } },
  { id: "rdl", name: "Romanian deadlift", equipment: "barbell", muscles: ["hamstrings", "glutes"], source: "library" },
  { id: "leg-curl", name: "Lying leg curl", equipment: "machine", muscles: ["hamstrings"], source: "library", lastSession: { date: day(4), sets: reps(40, 12, 11, 10) } },
  { id: "hip-thrust", name: "Hip thrust", equipment: "barbell", muscles: ["glutes", "hamstrings"], source: "library" },
  { id: "walking-lunge", name: "Walking lunge", equipment: "dumbbell", muscles: ["quads", "glutes"], source: "library" },
  { id: "calf-raise", name: "Standing calf raise", equipment: "machine", muscles: ["calves"], source: "library" },
  { id: "db-curl", name: "Dumbbell curl", equipment: "dumbbell", muscles: ["biceps"], source: "library", lastSession: { date: day(5), sets: reps(12, 12, 10, 9) } },
  { id: "hammer-curl", name: "Hammer curl", equipment: "dumbbell", muscles: ["biceps"], source: "library" },
  { id: "triceps-pushdown", name: "Triceps pushdown", equipment: "cable", muscles: ["triceps"], source: "library", lastSession: { date: day(2), sets: reps(25, 12, 12) } },
  { id: "skull-crusher", name: "EZ-bar skull crusher", equipment: "barbell", muscles: ["triceps"], source: "library" },
  { id: "plank", name: "Plank (seconds as reps)", equipment: "bodyweight", muscles: ["core"], source: "library" },
  { id: "cable-crunch", name: "Cable crunch", equipment: "cable", muscles: ["core"], source: "library" },
  { id: "kb-swing", name: "Kettlebell swing", equipment: "kettlebell", muscles: ["glutes", "hamstrings"], source: "library" },
  { id: "band-pull-apart", name: "Band pull-apart", equipment: "band", muscles: ["shoulders", "back"], source: "library" },
]
