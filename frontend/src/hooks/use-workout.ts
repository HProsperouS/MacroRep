import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { progressKeys, workoutKeys } from "@/api/query-keys"
import { workoutApi } from "@/api/workout-api"
import type { CreateExerciseInput, ExerciseFilters, FinishWorkoutInput } from "@/types/workout"

export function useTodayWorkout() {
  return useQuery({
    queryKey: workoutKeys.today(),
    queryFn: ({ signal }) => workoutApi.getToday(signal),
    staleTime: 5 * 60_000,
  })
}

export function useFinishWorkout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: FinishWorkoutInput) => workoutApi.finishSession(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workoutKeys.all })
      void queryClient.invalidateQueries({ queryKey: progressKeys.all })
    },
  })
}

export function useExerciseSearch(filters: ExerciseFilters) {
  return useQuery({
    queryKey: workoutKeys.exercises(filters),
    queryFn: ({ signal }) => workoutApi.searchExercises(filters, signal),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}

export function useCreateExercise() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateExerciseInput) => workoutApi.createExercise(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...workoutKeys.all, "exercises"] }),
  })
}
