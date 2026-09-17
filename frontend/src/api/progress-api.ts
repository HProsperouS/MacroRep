import { apiClient } from "@/api/client"
import type { DailyCalories, ProgressRange, ProgressResponse, WeighInInput, WeightPoint } from "@/types/progress"

export const progressApi = {
  async getProgress(range: ProgressRange, signal?: AbortSignal) {
    const { data } = await apiClient.get<ProgressResponse>("/progress", { params: { range }, signal })
    return data
  },

  async getDailyCalories(days: number, signal?: AbortSignal) {
    const { data } = await apiClient.get<DailyCalories[]>("/nutrition/daily-calories", { params: { days }, signal })
    return data
  },

  async addWeighIn(input: WeighInInput) {
    const { data } = await apiClient.post<WeightPoint>("/body/weigh-ins", input)
    return data
  },
}
