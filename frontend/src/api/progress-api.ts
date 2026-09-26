import { apiClient } from "@/api/client"
import type { DailyCalories, ProgressRange, ProgressResponse, WeighIn, WeighInInput, WeightPoint } from "@/types/progress"

export const progressApi = {
  async getProgress(range: ProgressRange, signal?: AbortSignal) {
    const { data } = await apiClient.get<ProgressResponse>("/progress", { params: { range }, signal })
    return data
  },

  async getDailyCalories(days: number, signal?: AbortSignal) {
    const { data } = await apiClient.get<DailyCalories[]>("/nutrition/daily-calories", { params: { days }, signal })
    return data
  },

  /** Saves the weight for a day, replacing any weigh-in already on that day. */
  async addWeighIn(input: WeighInInput) {
    const { data } = await apiClient.post<WeightPoint>("/body/weigh-ins", input)
    return data
  },

  /** Weigh-ins between two yyyy-MM-dd days (at most 366 days), newest first. */
  async listWeighIns(from: string, to: string, signal?: AbortSignal) {
    const { data } = await apiClient.get<WeighIn[]>("/body/weigh-ins", { params: { from, to }, signal })
    return data
  },

  /** Changes a weigh-in's weight and/or day; moving onto a day that already has one is a 409. */
  async updateWeighIn(weighInId: string, input: Partial<WeighInInput>) {
    const { data } = await apiClient.patch<WeighIn>(`/body/weigh-ins/${encodeURIComponent(weighInId)}`, input)
    return data
  },

  async deleteWeighIn(weighInId: string) {
    await apiClient.delete(`/body/weigh-ins/${encodeURIComponent(weighInId)}`)
  },
}
