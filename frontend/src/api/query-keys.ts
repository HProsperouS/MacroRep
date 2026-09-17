import type { ProgressRange } from "@/types/progress"
import type { ExerciseFilters } from "@/types/workout"

export const foodKeys = {
  all: ["food"] as const,
  log: (date: string) => [...foodKeys.all, "log", date] as const,
  search: (query: string) => [...foodKeys.all, "search", query] as const,
  targets: () => [...foodKeys.all, "targets"] as const,
  dailyCalories: (days: number) => [...foodKeys.all, "daily-calories", days] as const,
}

export const workoutKeys = {
  all: ["workout"] as const,
  today: () => [...workoutKeys.all, "today"] as const,
  exercises: (filters: ExerciseFilters) => [...workoutKeys.all, "exercises", filters] as const,
}

export const coachKeys = {
  all: ["coach"] as const,
  current: () => [...coachKeys.all, "current"] as const,
}

export const progressKeys = {
  all: ["progress"] as const,
  range: (range: ProgressRange) => [...progressKeys.all, range] as const,
}

export const profileKeys = {
  all: ["profile"] as const,
}
