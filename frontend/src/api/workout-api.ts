import { apiClient } from "@/api/client"
import type {
  CreateExerciseInput,
  Exercise,
  ExerciseFilters,
  FinishWorkoutInput,
  PlannedWorkout,
  SavePlanDayInput,
  WeekPlanDay,
  WorkoutSummary,
} from "@/types/workout"

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

  /** All 7 days of the user's weekly routine; a day's `plan` is null on a rest day. */
  async getWeekPlan(signal?: AbortSignal) {
    const { data } = await apiClient.get<WeekPlanDay[]>("/workouts/plan", { signal })
    return data
  },

  async savePlanDay(dayOfWeek: number, input: SavePlanDayInput) {
    const { data } = await apiClient.put<WeekPlanDay>(`/workouts/plan/${dayOfWeek}`, input)
    return data
  },

  /** Clears a day back to a rest day. */
  async deletePlanDay(dayOfWeek: number) {
    await apiClient.delete(`/workouts/plan/${dayOfWeek}`)
  },
}
