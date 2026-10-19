import { apiClient } from "@/api/client"
import type {
  CreateExerciseInput,
  Exercise,
  ExerciseFilters,
  FinishWorkoutInput,
  PlannedWorkout,
  Routine,
  SaveRoutineInput,
  UpdateWorkoutInput,
  WeekPlanDay,
  WorkoutDetail,
  WorkoutHistoryItem,
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

  /** Logged workouts, newest first. */
  async listSessions(offset: number, limit: number, signal?: AbortSignal) {
    const { data } = await apiClient.get<WorkoutHistoryItem[]>("/workouts/sessions", { params: { offset, limit }, signal })
    return data
  },

  async getSession(sessionId: string, signal?: AbortSignal) {
    const { data } = await apiClient.get<WorkoutDetail>(`/workouts/sessions/${encodeURIComponent(sessionId)}`, { signal })
    return data
  },

  async updateSession(sessionId: string, input: UpdateWorkoutInput) {
    const { data } = await apiClient.put<WorkoutDetail>(`/workouts/sessions/${encodeURIComponent(sessionId)}`, input)
    return data
  },

  async deleteSession(sessionId: string) {
    await apiClient.delete(`/workouts/sessions/${encodeURIComponent(sessionId)}`)
  },

  /** All 7 days of the user's weekly routine; a day's `plan` is null on a rest day. */
  async getWeekPlan(signal?: AbortSignal) {
    const { data } = await apiClient.get<WeekPlanDay[]>("/workouts/plan", { signal })
    return data
  },

  async listRoutines(signal?: AbortSignal) {
    const { data } = await apiClient.get<Routine[]>("/workouts/routines", { signal })
    return data
  },

  async createRoutine(input: SaveRoutineInput) {
    const { data } = await apiClient.post<Routine>("/workouts/routines", input)
    return data
  },

  async updateRoutine(routineId: string, input: SaveRoutineInput) {
    const { data } = await apiClient.put<Routine>(`/workouts/routines/${encodeURIComponent(routineId)}`, input)
    return data
  },

  /** Also takes the routine off the schedule; workouts already logged from it stay in history. */
  async deleteRoutine(routineId: string) {
    await apiClient.delete(`/workouts/routines/${encodeURIComponent(routineId)}`)
  },

  /** Schedules a routine on a weekday, replacing whatever was there. */
  async assignDay(dayOfWeek: number, routineId: string) {
    const { data } = await apiClient.put<WeekPlanDay>(`/workouts/plan/${dayOfWeek}`, { routineId })
    return data
  },

  /** Makes a weekday a rest day. The routine is kept. */
  async deletePlanDay(dayOfWeek: number) {
    await apiClient.delete(`/workouts/plan/${dayOfWeek}`)
  },
}
