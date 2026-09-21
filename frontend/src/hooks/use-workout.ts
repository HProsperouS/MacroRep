import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { progressKeys, workoutKeys } from "@/api/query-keys"
import { workoutApi } from "@/api/workout-api"
import type { CreateExerciseInput, ExerciseFilters, FinishWorkoutInput, SavePlanDayInput } from "@/types/workout"

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

export function useWeekPlan() {
  return useQuery({
    queryKey: workoutKeys.plan(),
    queryFn: ({ signal }) => workoutApi.getWeekPlan(signal),
    staleTime: 60_000,
  })
}

export function useSavePlanDay() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ dayOfWeek, input }: { dayOfWeek: number; input: SavePlanDayInput }) =>
      workoutApi.savePlanDay(dayOfWeek, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workoutKeys.plan() })
      void queryClient.invalidateQueries({ queryKey: workoutKeys.today() })
    },
  })
}

export function useDeletePlanDay() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dayOfWeek: number) => workoutApi.deletePlanDay(dayOfWeek),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: workoutKeys.plan() })
      void queryClient.invalidateQueries({ queryKey: workoutKeys.today() })
    },
  })
}
