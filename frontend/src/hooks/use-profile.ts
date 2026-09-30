import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef } from "react"

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

function browserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null
  } catch {
    return null
  }
}

/**
 * Keeps the profile's timezone in step with this device, so "today" and which day a workout
 * lands on follow the user's own clock (including when they travel). Tries once per page load:
 * a zone the server doesn't recognise is left alone, and the server keeps using the stored one.
 */
export function useSyncTimezone() {
  const queryClient = useQueryClient()
  const profile = useProfile()
  const attempted = useRef(false)
  const { mutate } = useMutation({
    mutationFn: (timezone: string) => profileApi.setTimezone(timezone),
    onSuccess: (updated) => {
      queryClient.setQueryData(profileKeys.all, updated)
      // Everything dated by the server can move to a different day.
      void queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== profileKeys.all[0] })
    },
  })

  const stored = profile.data?.timezone
  useEffect(() => {
    const current = browserTimezone()
    if (stored === undefined || current === null || stored === current || attempted.current) return
    attempted.current = true
    mutate(current)
  }, [stored, mutate])
}

export function useUpdateTargets() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: DailyTargets) => profileApi.updateTargets(input),
    onSuccess: (targets) => {
      queryClient.setQueryData(foodKeys.targets(), targets)
      // Days are judged complete or partial, and the gap measured, against the calorie target.
      void queryClient.invalidateQueries({ queryKey: [...foodKeys.all, "daily-calories"] })
      void queryClient.invalidateQueries({ queryKey: progressKeys.all })
    },
  })
}
