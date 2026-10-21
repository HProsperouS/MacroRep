import { z } from "zod"

import { toNumber } from "@/lib/format"
import { caloriesImplausiblyLow, implausibleCaloriesMessage } from "@/lib/macros"
import { requiredNumber } from "@/lib/zod-helpers"
import { EXPERIENCE_LEVELS, GOALS, type Goal, type UpdateProfileInput } from "@/types/profile"
import { EQUIPMENT } from "@/types/workout"

/** The Profile page's form and the sign-up guide share these rules. */
export const profileSchema = z.object({
  name: z.string().trim().min(1, "Enter your name").max(60, "Keep it under 60 characters"),
  heightCm: requiredNumber("your height", 100, 250),
  goal: z.enum(GOALS),
  // No health limit by design (see RateField's caution); 99.99 is what the server can store.
  weeklyRate: requiredNumber("a weekly rate", 0, 99.99),
  trainingDaysPerWeek: z.preprocess(
    (value) => (value === "" || value == null ? undefined : Number(value)),
    z
      .number({ required_error: "Enter your training days", invalid_type_error: "Enter a number" })
      .int("Whole days only")
      .min(1, "At least 1 day")
      .max(7, "At most 7 days"),
  ),
  experienceLevel: z.enum(EXPERIENCE_LEVELS),
  equipment: z.array(z.enum(EQUIPMENT)),
})

/** The weekly rate as stored: negative when losing, zero when maintaining. */
export function signedRate(goal: Goal, rate: number) {
  return goal === "maintain" ? 0 : goal === "lose" ? -rate : rate
}

/** The profile as the API takes it, from either form's values. */
export function toUpdateProfileInput(values: z.output<typeof profileSchema>): UpdateProfileInput {
  return {
    name: values.name,
    heightCm: values.heightCm,
    goal: values.goal,
    weeklyRateKg: signedRate(values.goal, values.weeklyRate),
    trainingDaysPerWeek: values.trainingDaysPerWeek,
    experienceLevel: values.experienceLevel,
    equipment: values.equipment,
  }
}

/** A body weight, in the same 20–400 kg range the server accepts (weigh-ins and the sign-up guide). */
export const bodyWeightKg = z.preprocess(
  (value) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN),
  z.number({ required_error: "Enter your weight", invalid_type_error: "Enter a number" }).min(20, "That looks too low").max(400, "That looks too high"),
)

export const targetsFields = z.object({
  calories: requiredNumber("calories", 1000, 6000),
  protein: requiredNumber("protein", 0, 500),
  carbs: requiredNumber("carbs", 0, 1000),
  fat: requiredNumber("fat", 0, 400),
})

/** Calories far below what the macros add up to are refused, as the server does. */
export function checkTargetCalories(v: z.output<typeof targetsFields>, ctx: z.RefinementCtx) {
  if (caloriesImplausiblyLow(v.calories, v)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, message: implausibleCaloriesMessage(v), path: ["calories"] })
  }
}
