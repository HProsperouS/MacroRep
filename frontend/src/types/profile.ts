export const GOALS = ["lose", "maintain", "gain"] as const
export type Goal = (typeof GOALS)[number]

export const GOAL_LABELS: Record<Goal, string> = {
  lose: "Lose fat",
  maintain: "Maintain",
  gain: "Build muscle",
}

export type Profile = {
  name: string
  email: string
  heightCm: number
  goal: Goal
  /** Target change per week in kg; negative when losing. */
  weeklyRateKg: number
  trainingDaysPerWeek: number
}

export type UpdateProfileInput = Omit<Profile, "email">
