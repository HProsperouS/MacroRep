import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"

import { foodApi, type CreateCustomFoodInput, type FoodLogResponse } from "@/api/food-api"
import { foodKeys } from "@/api/query-keys"
import type { FoodEntry } from "@/types/food"

export function dateKey(date: Date) {
  return format(date, "yyyy-MM-dd")
}

export function useFoodLog(date: Date) {
  const key = dateKey(date)
  return useQuery({
    queryKey: foodKeys.log(key),
    queryFn: ({ signal }) => foodApi.getFoodLog(key, signal),
  })
}

export function useNutritionTargets() {
  return useQuery({
    queryKey: foodKeys.targets(),
    queryFn: ({ signal }) => foodApi.getTargets(signal),
    staleTime: 5 * 60_000,
  })
}

export function useFoodSearch(query: string) {
  const q = query.trim()
  return useQuery({
    queryKey: foodKeys.search(q),
    queryFn: ({ signal }) => foodApi.searchFoods(q, signal),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

/** Adds an entry optimistically; rolls back if the request fails. */
export function useAddFoodEntry(date: Date) {
  const queryClient = useQueryClient()
  const key = dateKey(date)
  const queryKey = foodKeys.log(key)

  return useMutation({
    mutationFn: (entry: Omit<FoodEntry, "id">) => foodApi.addEntry({ ...entry, date: key }),
    onMutate: async (entry) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<FoodLogResponse>(queryKey)
      const optimistic: FoodEntry = { ...entry, id: `optimistic-${Date.now()}` }
      queryClient.setQueryData<FoodLogResponse>(queryKey, (old) => ({
        date: key,
        entries: [...(old?.entries ?? []), optimistic],
      }))
      return { previous }
    },
    onError: (_error, _entry, context) => {
      queryClient.setQueryData(queryKey, context?.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })
}

/** Removes an entry optimistically; rolls back if the request fails. */
export function useRemoveFoodEntry(date: Date) {
  const queryClient = useQueryClient()
  const queryKey = foodKeys.log(dateKey(date))

  return useMutation({
    mutationFn: (entryId: string) => foodApi.removeEntry(entryId),
    onMutate: async (entryId) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<FoodLogResponse>(queryKey)
      queryClient.setQueryData<FoodLogResponse>(queryKey, (old) =>
        old ? { ...old, entries: old.entries.filter((entry) => entry.id !== entryId) } : old,
      )
      return { previous }
    },
    onError: (_error, _entryId, context) => {
      queryClient.setQueryData(queryKey, context?.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  })
}

export function useCreateCustomFood() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateCustomFoodInput) => foodApi.createCustomFood(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...foodKeys.all, "search"] }),
  })
}
