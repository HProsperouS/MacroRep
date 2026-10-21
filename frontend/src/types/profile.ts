import type { DailyTargets } from "@/types/food"

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

export const SEXES = ["male", "female"] as const
export type Sex = (typeof SEXES)[number]

export const SEX_LABELS: Record<Sex, string> = {
  male: "Male",
  female: "Female",
}

export const ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "very"] as const
export type ActivityLevel = (typeof ACTIVITY_LEVELS)[number]

/** Daily activity, training included: it picks the factor resting energy is multiplied by. */
export const ACTIVITY_LEVEL_LABELS: Record<ActivityLevel, string> = {
  sedentary: "Mostly sitting, little exercise",
  light: "Lightly active, exercise 1–3 days a week",
  moderate: "Moderately active, exercise 3–5 days a week",
  very: "Very active, hard exercise 6–7 days a week",
}

export type Profile = {
  name: string
  email: string
  heightCm: number
  goal: Goal
  /** Target change per week in kg; negative when losing. */
  weeklyRateKg: number
  experienceLevel: ExperienceLevel
  /** IANA timezone, e.g. "Asia/Singapore"; synced from the browser, decides the user's calendar days. */
  timezone: string
  /** False until the sign-up guide is finished; until then the app shows only the guide. */
  onboarded: boolean
  /** ISO date. These three are empty only before the sign-up guide. */
  dateOfBirth: string | null
  sex: Sex | null
  activityLevel: ActivityLevel | null
}

type EstimateDetails = { dateOfBirth: string; sex: Sex; activityLevel: ActivityLevel }

export type UpdateProfileInput = Omit<Profile, "email" | "timezone" | "onboarded" | keyof EstimateDetails> & EstimateDetails

/** What estimating starting targets needs, before any of it is saved. */
export type EstimateTargetsInput = EstimateDetails & Pick<Profile, "heightCm" | "goal" | "weeklyRateKg"> & { weightKg: number }

/** Estimated targets, with the steps that led to them (kcal a day). */
export type TargetEstimate = DailyTargets & {
  resting: number
  maintenance: number
  /** For the weekly goal: negative when losing. */
  adjustment: number
}

/** The sign-up guide: the profile, today's weight and the starting daily targets. */
export type OnboardingInput = UpdateProfileInput & { weightKg: number; targets: DailyTargets }
