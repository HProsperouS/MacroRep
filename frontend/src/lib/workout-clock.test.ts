import { describe, expect, it } from "vitest"

import { elapsedMs, pauseClock, resumeClock, savedTimes, type WorkoutClock } from "@/lib/workout-clock"

const running: WorkoutClock = { startedAt: 1_000, pausedAt: null, pausedMs: 0 }

describe("workout clock", () => {
  it("counts time from the start while running", () => {
    expect(elapsedMs(running, 11_000)).toBe(10_000)
  })

  it("freezes while paused", () => {
    const paused = pauseClock(running, 11_000)
    expect(elapsedMs(paused, 11_000)).toBe(10_000)
    expect(elapsedMs(paused, 500_000)).toBe(10_000)
  })

  it("leaves out the paused time once resumed", () => {
    const paused = pauseClock(running, 11_000)
    const { clock: resumed, pausedFor } = resumeClock(paused, 71_000)
    expect(pausedFor).toBe(60_000)
    expect(resumed).toMatchObject({ pausedAt: null, pausedMs: 60_000 })
    expect(elapsedMs(resumed, 81_000)).toBe(10_000 + 10_000)
  })

  it("adds up several pauses", () => {
    let clock = pauseClock(running, 11_000)
    clock = resumeClock(clock, 21_000).clock // paused 10 s
    clock = pauseClock(clock, 31_000)
    clock = resumeClock(clock, 61_000).clock // paused 30 s
    expect(clock.pausedMs).toBe(40_000)
    expect(elapsedMs(clock, 71_000)).toBe(70_000 - 40_000)
  })

  it("ignores pausing twice and resuming when not paused", () => {
    const paused = pauseClock(running, 11_000)
    expect(pauseClock(paused, 99_000)).toBe(paused)
    expect(resumeClock(running, 99_000)).toEqual({ clock: running, pausedFor: 0 })
  })

  it("saves the real start and a finish pulled earlier by the pauses, so the duration is the training time", () => {
    let clock = pauseClock(running, 11_000)
    clock = resumeClock(clock, 71_000).clock
    const { startedAt, finishedAt } = savedTimes(clock, 101_000)
    expect(startedAt).toBe(1_000)
    expect(finishedAt).toBe(41_000)
    expect(finishedAt - startedAt).toBe(elapsedMs(clock, 101_000))
  })

  it("never saves a finish later than now", () => {
    let clock = pauseClock(running, 11_000)
    clock = resumeClock(clock, 71_000).clock
    expect(savedTimes(clock, 101_000).finishedAt).toBeLessThanOrEqual(101_000)
  })

  it("saves a workout that was never paused as it happened", () => {
    expect(savedTimes(running, 51_000)).toEqual({ startedAt: 1_000, finishedAt: 51_000 })
  })

  it("ends at the moment of the pause when saved while paused", () => {
    const paused = pauseClock(running, 11_000)
    expect(savedTimes(paused, 900_000)).toEqual({ startedAt: 1_000, finishedAt: 11_000 })
  })
})
