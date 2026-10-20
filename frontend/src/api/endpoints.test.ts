import type { InternalAxiosRequestConfig } from "axios"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { authApi } from "@/api/auth-api"
import { apiClient } from "@/api/client"
import { coachApi } from "@/api/coach-api"
import { foodApi } from "@/api/food-api"
import { profileApi } from "@/api/profile-api"
import { progressApi } from "@/api/progress-api"
import { workoutApi } from "@/api/workout-api"

type Sent = { method?: string; url?: string; params?: unknown; body?: unknown; idempotencyKey?: unknown }

const originalAdapter = apiClient.defaults.adapter
let sent: Sent[]

/** Records each request and answers 200 with `{ ok: true }`. */
beforeEach(() => {
  sent = []
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    sent.push({
      method: config.method,
      url: config.url,
      params: config.params,
      body: typeof config.data === "string" ? JSON.parse(config.data) : config.data,
      idempotencyKey: config.headers.get("Idempotency-Key"),
    })
    return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config }
  }
})

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
})

const body = { any: "value" }

// Each wrapper against the route the backend serves (app/*/router.py).
const cases: [string, () => Promise<unknown>, Sent][] = [
  ["register", () => authApi.register(body as never), { method: "post", url: "/auth/register", body }],
  ["login", () => authApi.login(body as never), { method: "post", url: "/auth/login", body }],
  ["logout", () => authApi.logout(), { method: "post", url: "/auth/logout" }],

  ["food log", () => foodApi.getFoodLog("2026-10-20"), { method: "get", url: "/food-log", params: { date: "2026-10-20" } }],
  ["add entry", () => foodApi.addEntry(body as never), { method: "post", url: "/food-log/entries", body }],
  ["update entry", () => foodApi.updateEntry("e/1", body as never), { method: "patch", url: "/food-log/entries/e%2F1", body }],
  ["remove entry", () => foodApi.removeEntry("e1"), { method: "delete", url: "/food-log/entries/e1" }],
  ["search foods", () => foodApi.searchFoods("rice"), { method: "get", url: "/foods", params: { q: "rice", limit: 8 } }],
  ["get food", () => foodApi.getFood("f1"), { method: "get", url: "/foods/f1" }],
  ["create food", () => foodApi.createCustomFood(body as never), { method: "post", url: "/foods", body }],
  ["targets", () => foodApi.getTargets(), { method: "get", url: "/nutrition/targets" }],

  ["profile", () => profileApi.getProfile(), { method: "get", url: "/profile" }],
  ["update profile", () => profileApi.updateProfile(body as never), { method: "put", url: "/profile", body }],
  ["timezone", () => profileApi.setTimezone("Asia/Singapore"), { method: "put", url: "/profile/timezone", body: { timezone: "Asia/Singapore" } }],
  ["target history", () => profileApi.getTargetHistory(), { method: "get", url: "/nutrition/targets/history" }],
  ["update targets", () => profileApi.updateTargets(body as never), { method: "put", url: "/nutrition/targets", body }],

  ["progress", () => progressApi.getProgress("3M"), { method: "get", url: "/progress", params: { range: "3M" } }],
  ["daily calories", () => progressApi.getDailyCalories(7), { method: "get", url: "/nutrition/daily-calories", params: { days: 7 } }],
  ["add weigh-in", () => progressApi.addWeighIn(body as never), { method: "post", url: "/body/weigh-ins", body }],
  ["weigh-ins", () => progressApi.listWeighIns("2026-10-01", "2026-10-20"), { method: "get", url: "/body/weigh-ins", params: { from: "2026-10-01", to: "2026-10-20" } }],
  ["update weigh-in", () => progressApi.updateWeighIn("w1", body as never), { method: "patch", url: "/body/weigh-ins/w1", body }],
  ["delete weigh-in", () => progressApi.deleteWeighIn("w1"), { method: "delete", url: "/body/weigh-ins/w1" }],

  ["today", () => workoutApi.getToday(), { method: "get", url: "/workouts/today" }],
  [
    "exercises",
    () => workoutApi.searchExercises({ q: "press", muscle: "Chest", equipment: "barbell" } as never),
    { method: "get", url: "/exercises", params: { q: "press", muscle: "Chest", equipment: "barbell", limit: 30 } },
  ],
  ["create exercise", () => workoutApi.createExercise(body as never), { method: "post", url: "/exercises", body }],
  ["finish session", () => workoutApi.finishSession(body as never), { method: "post", url: "/workouts/sessions", body }],
  ["sessions", () => workoutApi.listSessions(20, 10), { method: "get", url: "/workouts/sessions", params: { offset: 20, limit: 10 } }],
  ["session", () => workoutApi.getSession("s1"), { method: "get", url: "/workouts/sessions/s1" }],
  ["update session", () => workoutApi.updateSession("s1", body as never), { method: "put", url: "/workouts/sessions/s1", body }],
  ["delete session", () => workoutApi.deleteSession("s1"), { method: "delete", url: "/workouts/sessions/s1" }],
  ["week plan", () => workoutApi.getWeekPlan(), { method: "get", url: "/workouts/plan" }],
  ["routines", () => workoutApi.listRoutines(), { method: "get", url: "/workouts/routines" }],
  ["create routine", () => workoutApi.createRoutine(body as never), { method: "post", url: "/workouts/routines", body }],
  ["update routine", () => workoutApi.updateRoutine("r1", body as never), { method: "put", url: "/workouts/routines/r1", body }],
  ["delete routine", () => workoutApi.deleteRoutine("r1"), { method: "delete", url: "/workouts/routines/r1" }],
  ["assign day", () => workoutApi.assignDay(3, "r1"), { method: "put", url: "/workouts/plan/3", body: { routineId: "r1" } }],
  ["rest day", () => workoutApi.deletePlanDay(3), { method: "delete", url: "/workouts/plan/3" }],

  ["current check-in", () => coachApi.getCurrentCheckIn(), { method: "get", url: "/coach/check-ins/current" }],
  ["start check-in", () => coachApi.startCheckIn("key-1"), { method: "post", url: "/coach/check-ins", idempotencyKey: "key-1" }],
  [
    "decide proposal",
    () => coachApi.decideProposal("c1", "p1", body as never),
    { method: "post", url: "/coach/check-ins/c1/proposals/p1/decision", body },
  ],
  ["messages", () => coachApi.listMessages("c1"), { method: "get", url: "/coach/check-ins/c1/messages" }],
  ["ask coach", () => coachApi.askCoach("c1", "Why?"), { method: "post", url: "/coach/check-ins/c1/messages", body: { text: "Why?" } }],
]

describe("API endpoints", () => {
  it.each(cases)("%s", async (_name, call, expected) => {
    await call()
    expect(sent).toHaveLength(1)
    expect(sent[0]).toMatchObject(expected)
  })
})
