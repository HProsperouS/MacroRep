import { beforeEach, describe, expect, it, vi } from "vitest"

import type { PlannedWorkout } from "@/types/workout"

const plan: PlannedWorkout = {
  id: "plan-1",
  name: "Push day",
  weekLabel: "Week 1",
  estimatedMinutes: 45,
  exercises: [
    {
      id: "bench",
      name: "Bench Press",
      equipment: "Barbell",
      muscles: "Chest",
      restSeconds: 90,
      sets: [{ id: "bench-0", kind: "working", targetWeightKg: 60, targetReps: 8 }],
    },
  ],
}

/** The store keeps its state in module variables, so each test loads a fresh copy (as a page reload would). */
async function loadStore() {
  vi.resetModules()
  return import("@/lib/active-workout-store")
}

beforeEach(() => {
  window.localStorage.clear()
  vi.useRealTimers()
})

describe("active workout store", () => {
  it("starts running, not paused", async () => {
    const store = await loadStore()
    store.beginWorkout(plan)
    expect(store.getActiveWorkout()).toMatchObject({ pausedAt: null, pausedMs: 0 })
  })

  it("pauses and resumes, adding up the paused time", async () => {
    const store = await loadStore()
    store.beginWorkout(plan)
    const startedAt = store.getActiveWorkout()!.startedAt

    store.pauseWorkout(startedAt + 10_000)
    expect(store.getActiveWorkout()?.pausedAt).toBe(startedAt + 10_000)

    store.resumeWorkout(startedAt + 70_000)
    expect(store.getActiveWorkout()).toMatchObject({ pausedAt: null, pausedMs: 60_000 })
  })

  it("pushes a running rest timer back by the length of the pause", async () => {
    const store = await loadStore()
    store.beginWorkout(plan)
    const startedAt = store.getActiveWorkout()!.startedAt
    store.updateActiveSession((session) => ({ ...session, rest: { endsAt: startedAt + 30_000, totalSeconds: 90 } }))

    store.pauseWorkout(startedAt + 10_000)
    store.resumeWorkout(startedAt + 100_000)

    expect(store.getActiveWorkout()?.session.rest).toEqual({ endsAt: startedAt + 30_000 + 90_000, totalSeconds: 90 })
  })

  it("keeps a rest that ran out before the pause finished", async () => {
    const store = await loadStore()
    store.beginWorkout(plan)
    const startedAt = store.getActiveWorkout()!.startedAt
    store.updateActiveSession((session) => ({ ...session, rest: { endsAt: startedAt + 5_000, totalSeconds: 90 } }))

    store.pauseWorkout(startedAt + 10_000) // the rest ended 5 s earlier
    store.resumeWorkout(startedAt + 100_000)

    expect(store.getActiveWorkout()?.session.rest?.endsAt).toBe(startedAt + 5_000)
  })

  it("ignores resume when not paused", async () => {
    const store = await loadStore()
    store.beginWorkout(plan)
    const before = store.getActiveWorkout()
    store.resumeWorkout(Date.now() + 60_000)
    expect(store.getActiveWorkout()).toBe(before)
  })

  it("stays paused across a reload", async () => {
    const first = await loadStore()
    first.beginWorkout(plan)
    first.pauseWorkout(first.getActiveWorkout()!.startedAt + 5_000)

    const reloaded = await loadStore()
    expect(reloaded.getActiveWorkout()?.pausedAt).toBe(first.getActiveWorkout()!.pausedAt)
    expect(reloaded.getActiveWorkout()?.session.exercises).toHaveLength(1)
  })

  it("loads a workout saved before pausing existed as running", async () => {
    window.localStorage.setItem(
      "macrorep.active-workout.v1",
      JSON.stringify({ v: 1, startedAt: 123, plan: null, session: { name: "Old", planId: null, exercises: [], rest: null, seq: 0 } }),
    )
    const store = await loadStore()
    expect(store.getActiveWorkout()).toMatchObject({ startedAt: 123, pausedAt: null, pausedMs: 0 })
  })

  it("ignores a stored workout with corrupt pause fields", async () => {
    window.localStorage.setItem(
      "macrorep.active-workout.v1",
      JSON.stringify({ v: 1, startedAt: 123, pausedAt: "yesterday", pausedMs: 0, plan: null, session: { name: "X", planId: null, exercises: [], rest: null, seq: 0 } }),
    )
    const store = await loadStore()
    expect(store.getActiveWorkout()).toBeNull()
  })

  it("does nothing to pause or resume when no workout is active", async () => {
    const store = await loadStore()
    store.pauseWorkout()
    store.resumeWorkout()
    expect(store.getActiveWorkout()).toBeNull()
  })
})
