import type { Equipment } from "@/types/workout"

export const GOALS = ["lose", "maintain", "gain"] as const
export type Goal = (typeof GOALS)[number]

export const GOAL_LABELS: Record<Goal, string> = {
  lose: "Lose fat",
  maintain: "Maintain",
  gain: "Build muscle",
}

export const EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"] as const
export type ExperienceLevel = (typeof EXPERIENCE_LEVELS)[number]

export const EXPERIENCE_LEVEL_LABELS: Record<ExperienceLevel, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
}

export type Profile = {
  name: string
  email: string
  heightCm: number
  goal: Goal
  /** Target change per week in kg; negative when losing. */
  weeklyRateKg: number
  trainingDaysPerWeek: number
  experienceLevel: ExperienceLevel
  /** Equipment the user has access to; steers what the coach proposes. */
  equipment: Equipment[]
}

export type UpdateProfileInput = Omit<Profile, "email">
