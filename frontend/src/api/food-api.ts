import { apiClient } from "@/api/client"
import type { Nutrition } from "@/lib/macros"
import type { DailyTargets, Food, FoodEntry, MealType, QuantityUnit } from "@/types/food"

export type FoodLogResponse = {
  date: string
  entries: FoodEntry[]
}

/** A saved food and an amount: the server derives the name, label and nutrition from the food. */
export type LogSavedFoodInput = { date: string; meal: MealType; foodId: string; quantity: number; quantityUnit: QuantityUnit }
/** A quick add: the values exactly as entered. */
export type LogEnteredValuesInput = Nutrition & { date: string; meal: MealType; name: string; amountLabel: string; source: FoodEntry["source"] }
export type CreateFoodEntryInput = LogSavedFoodInput | LogEnteredValuesInput

/**
 * Fields to change. `date` and `meal` apply to any entry; a saved food's entry changes its
 * quantity, a quick add its values.
 */
export type UpdateFoodEntryInput = Partial<Nutrition & { date: string; meal: MealType; name: string; quantity: number; quantityUnit: QuantityUnit }>

export type CreateCustomFoodInput = Omit<Food, "id" | "source">

/** Typed wrappers around the food endpoints. Paths mirror the planned FastAPI routes. */
export const foodApi = {
  async getFoodLog(date: string, signal?: AbortSignal) {
    const { data } = await apiClient.get<FoodLogResponse>("/food-log", { params: { date }, signal })
    return data
  },

  async addEntry(input: CreateFoodEntryInput) {
    const { data } = await apiClient.post<FoodEntry>("/food-log/entries", input)
    return data
  },

  async updateEntry(entryId: string, input: UpdateFoodEntryInput) {
    const { data } = await apiClient.patch<FoodEntry>(`/food-log/entries/${encodeURIComponent(entryId)}`, input)
    return data
  },

  async removeEntry(entryId: string) {
    await apiClient.delete(`/food-log/entries/${encodeURIComponent(entryId)}`)
  },

  async searchFoods(query: string, signal?: AbortSignal) {
    const { data } = await apiClient.get<Food[]>("/foods", { params: { q: query, limit: 8 }, signal })
    return data
  },

  async getFood(foodId: string, signal?: AbortSignal) {
    const { data } = await apiClient.get<Food>(`/foods/${encodeURIComponent(foodId)}`, { signal })
    return data
  },

  async createCustomFood(input: CreateCustomFoodInput) {
    const { data } = await apiClient.post<Food>("/foods", input)
    return data
  },

  async getTargets(signal?: AbortSignal) {
    const { data } = await apiClient.get<DailyTargets>("/nutrition/targets", { signal })
    return data
  },
}
