import { apiClient } from "@/api/client"
import type { DailyTargets, Food, FoodEntry } from "@/types/food"

export type FoodLogResponse = {
  date: string
  entries: FoodEntry[]
}

export type CreateFoodEntryInput = Omit<FoodEntry, "id"> & { date: string }
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

  async removeEntry(entryId: string) {
    await apiClient.delete(`/food-log/entries/${encodeURIComponent(entryId)}`)
  },

  async searchFoods(query: string, signal?: AbortSignal) {
    const { data } = await apiClient.get<Food[]>("/foods", { params: { q: query, limit: 8 }, signal })
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
