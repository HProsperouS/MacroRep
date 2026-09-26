import type { ProgressRange } from "@/types/progress"
import type { ExerciseFilters } from "@/types/workout"

export const foodKeys = {
  all: ["food"] as const,
  logs: () => [...foodKeys.all, "log"] as const,
  log: (date: string) => [...foodKeys.logs(), date] as const,
  search: (query: string) => [...foodKeys.all, "search", query] as const,
  food: (foodId: string) => [...foodKeys.all, "food", foodId] as const,
  targets: () => [...foodKeys.all, "targets"] as const,
  dailyCalories: (days: number) => [...foodKeys.all, "daily-calories", days] as const,
}

export const workoutKeys = {
  all: ["workout"] as const,
  today: () => [...workoutKeys.all, "today"] as const,
  exercises: (filters: ExerciseFilters) => [...workoutKeys.all, "exercises", filters] as const,
  plan: () => [...workoutKeys.all, "plan"] as const,
}

export const coachKeys = {
  all: ["coach"] as const,
  current: () => [...coachKeys.all, "current"] as const,
}

export const progressKeys = {
  all: ["progress"] as const,
  range: (range: ProgressRange) => [...progressKeys.all, range] as const,
}

export const bodyKeys = {
  all: ["body"] as const,
  weighIns: (from: string, to: string) => [...bodyKeys.all, "weigh-ins", from, to] as const,
}

export const profileKeys = {
  all: ["profile"] as const,
}
