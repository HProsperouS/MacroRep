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

export type FoodSource = "database" | "custom" | "quick-add"

/** A food that can be searched and logged. Nutrition is per one serving. */
export type Food = {
  id: string
  name: string
  brand?: string
  servingSize: number
  servingUnit: ServingUnit
  /** Weight of one serving in grams, when known — enables logging by grams. */
  servingWeightG?: number
  nutrition: Nutrition
  fibreG?: number
  sugarG?: number
  sodiumMg?: number
  source: Exclude<FoodSource, "quick-add">
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
