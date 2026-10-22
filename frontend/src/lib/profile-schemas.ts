import { z } from "zod"

import { toNumber } from "@/lib/format"
import { caloriesImplausiblyLow, implausibleCaloriesMessage } from "@/lib/macros"
import { requiredNumber } from "@/lib/zod-helpers"
import { ACTIVITY_LEVELS, EXPERIENCE_LEVELS, GOALS, SEXES, type Goal, type UpdateProfileInput } from "@/types/profile"

// Ages the target estimate's formula is meant for, as the server allows.
const MIN_AGE = 13
const MAX_AGE = 100

/** Whole years from a yyyy-MM-dd birth date to today, or undefined for anything else. */
function ageFrom(birthDate: string, today = new Date()) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(birthDate)
  if (!match) return undefined
  const [year, month, day] = match.slice(1).map(Number)
  const birthdayPassed = today.getMonth() + 1 > month || (today.getMonth() + 1 === month && today.getDate() >= day)
  return today.getFullYear() - year - (birthdayPassed ? 0 : 1)
}

/** The Profile page's form and the sign-up guide share these rules. */
export const profileSchema = z.object({
  name: z.string().trim().min(1, "Enter your name").max(60, "Keep it under 60 characters"),
  heightCm: requiredNumber("your height", 100, 250),
  goal: z.enum(GOALS),
  // No health limit by design (see RateField's caution); 99.99 is what the server can store.
  weeklyRate: requiredNumber("a weekly rate", 0, 99.99),
  experienceLevel: z.enum(EXPERIENCE_LEVELS),
  dateOfBirth: z
    .string()
    .min(1, "Enter your date of birth")
    .refine((value) => {
      const age = ageFrom(value)
      return age !== undefined && age >= MIN_AGE && age <= MAX_AGE
    }, `You need to be ${MIN_AGE}–${MAX_AGE} years old`),
  sex: z.enum(SEXES, { required_error: "Choose one" }),
  activityLevel: z.enum(ACTIVITY_LEVELS, { required_error: "Choose how active you are" }),
})

/** The rate a new form starts with, in kg a week. */
export const DEFAULT_WEEKLY_RATE = "0.5"

/** After the goal changes. Maintaining hides the rate, so one typed in for another goal mustn't
 * block the form with an error the user can't see: it goes back to the default. */
export function resetRateIfMaintaining(
  goal: Goal,
  setValue: (name: "weeklyRate", value: string) => void,
  clearErrors: (name: "weeklyRate") => void,
) {
  if (goal !== "maintain") return
  setValue("weeklyRate", DEFAULT_WEEKLY_RATE)
  clearErrors("weeklyRate")
}

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
    experienceLevel: values.experienceLevel,
    dateOfBirth: values.dateOfBirth,
    sex: values.sex,
    activityLevel: values.activityLevel,
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
