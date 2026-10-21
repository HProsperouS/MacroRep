import type { Nutrition } from "@/lib/macros"

export const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snacks"] as const
export type MealType = (typeof MEAL_TYPES)[number]

export const MEAL_LABELS: Record<MealType, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner",
  snacks: "Snacks",
}

export const SERVING_UNITS = ["g", "ml", "piece", "bowl", "plate", "cup", "slice", "tbsp", "scoop"] as const
export type ServingUnit = (typeof SERVING_UNITS)[number]

export type FoodSource = "database" | "custom" | "quick-add" | "photo"

/** Foods to offer before a search: what the user ate lately, then other foods to fill up. */
export type FoodSuggestions = { recent: Food[]; common: Food[] }

/** A food that can be searched and logged. Nutrition is per one serving. */
export type Food = {
  id: string
  name: string
  servingSize: number
  servingUnit: ServingUnit
  /** Weight of one serving in grams, when known — enables logging by grams. */
  servingWeightG?: number
  nutrition: Nutrition
  source: Exclude<FoodSource, "quick-add" | "photo">
}

/** How a logged amount was entered: a count of the food's servings, or grams. */
export type QuantityUnit = "serving" | "g"

/** One logged item in a day's food log. */
export type FoodEntry = Nutrition & {
  id: string
  meal: MealType
  name: string
  amountLabel: string
  source: FoodSource
  /** Set when logged from a saved food: editing the quantity re-scales the nutrition. */
  foodId?: string | null
  quantity?: number | null
  quantityUnit?: QuantityUnit | null
}

export type DailyTargets = Nutrition

export type TargetSource = "initial" | "manual" | "check-in"

/** One version of the daily targets. A change adds a version rather than overwriting the last. */
export type TargetVersion = DailyTargets & {
  version: number
  /** yyyy-MM-dd: the first day these targets applied to. */
  effectiveDate: string
  source: TargetSource
  /** ISO timestamp in UTC. */
  changedAt: string
}

/** One food a meal photo seems to hold, estimated by the model for the user to correct. */
export type PhotoItem = Nutrition & {
  name: string
  /** How the portion looks, e.g. "1 cup". */
  portion: string
  grams: number
}

export type PhotoEstimate = {
  /** Empty when no food was recognised. */
  items: PhotoItem[]
  /** What the model couldn't judge, or why it found nothing. */
  note: string | null
}
