/**
 * The stopwatch of a live workout. Pausing remembers when the pause began;
 * resuming adds the length of the pause to `pausedMs`, which is then left out
 * of the elapsed time. Pure so it can be tested without a clock.
 */
export type WorkoutClock = {
  /** Epoch ms when the workout was started. */
  startedAt: number
  /** Epoch ms when the current pause began, or null while running. */
  pausedAt: number | null
  /** Total length of earlier, finished pauses. */
  pausedMs: number
}

/** Time spent training: frozen while paused, and never counting earlier pauses. */
export function elapsedMs(clock: WorkoutClock, now: number) {
  return Math.max(0, (clock.pausedAt ?? now) - clock.startedAt - clock.pausedMs)
}

export function pauseClock<T extends WorkoutClock>(clock: T, now: number): T {
  return clock.pausedAt === null ? { ...clock, pausedAt: now } : clock
}

/** Returns the resumed clock and how long the pause lasted, so callers can push other deadlines back by as much. */
export function resumeClock<T extends WorkoutClock>(clock: T, now: number): { clock: T; pausedFor: number } {
  if (clock.pausedAt === null) return { clock, pausedFor: 0 }
  const pausedFor = Math.max(0, now - clock.pausedAt)
  return { clock: { ...clock, pausedAt: null, pausedMs: clock.pausedMs + pausedFor }, pausedFor }
}

/**
 * Start and finish times to save, with pauses taken out. The real start is kept,
 * because it decides which day the workout belongs to; the finish is pulled
 * earlier by the paused time, so finish minus start is the time spent training.
 */
export function savedTimes(clock: WorkoutClock, now: number) {
  return { startedAt: clock.startedAt, finishedAt: clock.startedAt + elapsedMs(clock, now) }
}
