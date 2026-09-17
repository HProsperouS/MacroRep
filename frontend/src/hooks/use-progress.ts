import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { progressApi } from "@/api/progress-api"
import { foodKeys, progressKeys } from "@/api/query-keys"
import type { ProgressRange, WeighInInput } from "@/types/progress"

export function useProgress(range: ProgressRange) {
  return useQuery({
    queryKey: progressKeys.range(range),
    queryFn: ({ signal }) => progressApi.getProgress(range, signal),
    placeholderData: keepPreviousData,
  })
}

export function useDailyCalories(days: number) {
  return useQuery({
    queryKey: foodKeys.dailyCalories(days),
    queryFn: ({ signal }) => progressApi.getDailyCalories(days, signal),
  })
}

export function useAddWeighIn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: WeighInInput) => progressApi.addWeighIn(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: progressKeys.all }),
  })
}
