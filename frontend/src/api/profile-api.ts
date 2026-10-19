import { apiClient } from "@/api/client"
import type { DailyTargets, TargetVersion } from "@/types/food"
import type { Profile, UpdateProfileInput } from "@/types/profile"

export const profileApi = {
  async getProfile(signal?: AbortSignal) {
    const { data } = await apiClient.get<Profile>("/profile", { signal })
    return data
  },

  async updateProfile(input: UpdateProfileInput) {
    const { data } = await apiClient.put<Profile>("/profile", input)
    return data
  },

  async setTimezone(timezone: string) {
    const { data } = await apiClient.put<Profile>("/profile/timezone", { timezone })
    return data
  },

  /** Every version of the targets, newest first. */
  async getTargetHistory(signal?: AbortSignal) {
    const { data } = await apiClient.get<TargetVersion[]>("/nutrition/targets/history", { signal })
    return data
  },

  async updateTargets(input: DailyTargets) {
    const { data } = await apiClient.put<DailyTargets>("/nutrition/targets", input)
    return data
  },
}
