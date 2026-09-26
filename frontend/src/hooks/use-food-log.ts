import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"

import { foodApi, type CreateCustomFoodInput, type CreateFoodEntryInput, type FoodLogResponse, type UpdateFoodEntryInput } from "@/api/food-api"
import { foodKeys } from "@/api/query-keys"
import type { FoodEntry } from "@/types/food"

type NewFoodEntry = Omit<FoodEntry, "id">

/**
 * A saved food's entry is sent as food + quantity only; the server derives the rest, so the
 * locally computed values are just the optimistic preview.
 */
function toCreateInput(entry: NewFoodEntry, date: string): CreateFoodEntryInput {
  if (entry.foodId && entry.quantity != null) {
    return { date, meal: entry.meal, foodId: entry.foodId, quantity: entry.quantity, quantityUnit: entry.quantityUnit ?? "serving" }
  }
  const { meal, name, amountLabel, source, calories, protein, carbs, fat } = entry
  return { date, meal, name, amountLabel, source, calories, protein, carbs, fat }
}

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
    mutationFn: (entry: NewFoodEntry) => foodApi.addEntry(toCreateInput(entry, key)),
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

/** Edits an entry. Not optimistic: a saved food's nutrition is only known once the server re-scales it. */
export function useUpdateFoodEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ entryId, input }: { entryId: string; input: UpdateFoodEntryInput }) => foodApi.updateEntry(entryId, input),
    // Every day's log, not just this one: the entry may have moved to another day.
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: foodKeys.logs() }),
        queryClient.invalidateQueries({ queryKey: [...foodKeys.all, "daily-calories"] }),
      ]),
  })
}

/** A single saved food, for re-scaling an entry logged from it. */
export function useFood(foodId: string | null | undefined) {
  return useQuery({
    queryKey: foodKeys.food(foodId ?? ""),
    queryFn: ({ signal }) => foodApi.getFood(foodId as string, signal),
    enabled: Boolean(foodId),
    staleTime: 5 * 60_000,
  })
}

export function useCreateCustomFood() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateCustomFoodInput) => foodApi.createCustomFood(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...foodKeys.all, "search"] }),
  })
}
