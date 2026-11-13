import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query"

import { progressApi } from "@/api/progress-api"
import { bodyKeys, foodKeys, progressKeys } from "@/api/query-keys"
import type { ProgressRange, WeighInInput } from "@/types/progress"

export function useProgress(range: ProgressRange) {
  return useQuery({
    queryKey: progressKeys.range(range),
    queryFn: ({ signal }) => progressApi.getProgress(range, signal),
    placeholderData: keepPreviousData,
  })
}

/** The latest scale weight in the past month, which bodyweight sets count as their load
 *  during a workout (the server uses the latest weigh-in on record when it's saved). */
export function useLatestBodyWeight() {
  const progress = useProgress("1M")
  return progress.data?.weight.points.findLast((point) => point.scaleKg != null)?.scaleKg ?? null
}

export function useDailyCalories(days: number) {
  return useQuery({
    queryKey: foodKeys.dailyCalories(days),
    queryFn: ({ signal }) => progressApi.getDailyCalories(days, signal),
  })
}

export function useWeighIns(from: string, to: string) {
  return useQuery({
    queryKey: bodyKeys.weighIns(from, to),
    queryFn: ({ signal }) => progressApi.listWeighIns(from, to, signal),
    placeholderData: keepPreviousData,
  })
}

/** Any weigh-in change moves the trend, so both the dashboard and the list refetch. */
function refreshWeight(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: progressKeys.all }),
    queryClient.invalidateQueries({ queryKey: bodyKeys.all }),
  ])
}

export function useAddWeighIn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: WeighInInput) => progressApi.addWeighIn(input),
    onSuccess: () => refreshWeight(queryClient),
  })
}

export function useUpdateWeighIn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ weighInId, input }: { weighInId: string; input: Partial<WeighInInput> }) => progressApi.updateWeighIn(weighInId, input),
    onSuccess: () => refreshWeight(queryClient),
  })
}

export function useDeleteWeighIn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (weighInId: string) => progressApi.deleteWeighIn(weighInId),
    onSuccess: () => refreshWeight(queryClient),
  })
}
