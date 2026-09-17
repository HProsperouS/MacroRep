import type { Nutrition } from "@/lib/macros"
import { MEAL_TYPES, type FoodEntry, type MealType } from "@/types/food"

export const EMPTY_ENTRIES: FoodEntry[] = []

/** Totals and per-meal grouping in a single pass over the day's entries. */
export function groupEntries(entries: FoodEntry[]) {
  const totals: Nutrition = { calories: 0, protein: 0, carbs: 0, fat: 0 }
  const byMeal = Object.fromEntries(MEAL_TYPES.map((meal) => [meal, [] as FoodEntry[]])) as Record<MealType, FoodEntry[]>

  for (const entry of entries) {
    totals.calories += entry.calories
    totals.protein += entry.protein
    totals.carbs += entry.carbs
    totals.fat += entry.fat
    byMeal[entry.meal].push(entry)
  }

  return { totals, byMeal }
}

export function mealForTime(date: Date): MealType {
  const hour = date.getHours()
  if (hour < 10) return "breakfast"
  if (hour < 15) return "lunch"
  if (hour < 21) return "dinner"
  return "snacks"
}
