import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { profileApi } from "@/api/profile-api"
import { foodKeys, profileKeys, progressKeys } from "@/api/query-keys"
import type { DailyTargets } from "@/types/food"
import type { UpdateProfileInput } from "@/types/profile"

export function useProfile() {
  return useQuery({
    queryKey: profileKeys.all,
    queryFn: ({ signal }) => profileApi.getProfile(signal),
    staleTime: 5 * 60_000,
  })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdateProfileInput) => profileApi.updateProfile(input),
    onSuccess: (profile) => {
      queryClient.setQueryData(profileKeys.all, profile)
      // Goal rate feeds the progress page.
      void queryClient.invalidateQueries({ queryKey: progressKeys.all })
    },
  })
}

export function useUpdateTargets() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: DailyTargets) => profileApi.updateTargets(input),
    onSuccess: (targets) => queryClient.setQueryData(foodKeys.targets(), targets),
  })
}
