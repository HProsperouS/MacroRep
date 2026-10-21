import { apiClient } from "@/api/client"
import type { DailyTargets, TargetVersion } from "@/types/food"
import type { OnboardingInput, Profile, UpdateProfileInput } from "@/types/profile"

export const profileApi = {
  async getProfile(signal?: AbortSignal) {
    const { data } = await apiClient.get<Profile>("/profile", { signal })
    return data
  },

  async updateProfile(input: UpdateProfileInput) {
    const { data } = await apiClient.put<Profile>("/profile", input)
    return data
  },

  /** Saves the sign-up guide in one go; refused (409) once it's been finished. */
  async completeOnboarding(input: OnboardingInput) {
    const { data } = await apiClient.post<Profile>("/profile/onboarding", input)
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
