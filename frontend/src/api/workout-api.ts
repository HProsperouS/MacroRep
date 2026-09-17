import { apiClient } from "@/api/client"
import type { CreateExerciseInput, Exercise, ExerciseFilters, FinishWorkoutInput, PlannedWorkout, WorkoutSummary } from "@/types/workout"

export const workoutApi = {
  /** Today's planned session, or null on a rest day. */
  async getToday(signal?: AbortSignal) {
    const { data } = await apiClient.get<PlannedWorkout | null>("/workouts/today", { signal })
    return data
  },

  async searchExercises({ q, muscle, equipment }: ExerciseFilters, signal?: AbortSignal) {
    const { data } = await apiClient.get<Exercise[]>("/exercises", { params: { q, muscle, equipment, limit: 30 }, signal })
    return data
  },

  async createExercise(input: CreateExerciseInput) {
    const { data } = await apiClient.post<Exercise>("/exercises", input)
    return data
  },

  async finishSession(input: FinishWorkoutInput) {
    const { data } = await apiClient.post<WorkoutSummary>("/workouts/sessions", input)
    return data
  },
}
