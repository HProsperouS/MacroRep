import { pauseClock, resumeClock, type WorkoutClock } from "@/lib/workout-clock"
import { initSession, type SessionState } from "@/lib/workout-session"
import type { PlannedWorkout, StrengthHighlight } from "@/types/workout"

/**
 * The in-progress workout, kept outside React so it survives leaving the page,
 * reloads and closing the tab. Persisted to localStorage (versioned key);
 * falls back to memory when storage is unavailable (private mode, blocked).
 * Other tabs stay in sync through the `storage` event.
 *
 * Backend note: every change goes through `set()`, so server-side sessions
 * (POST on start, PATCH on change, so a workout follows the user across devices)
 * can be added there, keeping this storage as the offline fallback.
 */

export type ActiveWorkout = WorkoutClock & {
  session: SessionState
  /** Display context from the plan; null for an empty workout. */
  plan: { highlight?: StrengthHighlight } | null
}

type StoredWorkout = ActiveWorkout & { v: 1 }

const STORAGE_KEY = "macrorep.active-workout.v1"

const listeners = new Set<() => void>()
let loaded = false
let current: ActiveWorkout | null = null

function isStoredWorkout(value: unknown): value is StoredWorkout {
  if (typeof value !== "object" || value === null) return false
  const candidate = value as Partial<StoredWorkout>
  // Workouts saved before pausing existed have neither pause field; anything else must be a number.
  const pauseFieldsOk =
    (candidate.pausedAt === undefined || candidate.pausedAt === null || Number.isFinite(candidate.pausedAt)) &&
    (candidate.pausedMs === undefined || Number.isFinite(candidate.pausedMs))
  return candidate.v === 1 && typeof candidate.startedAt === "number" && pauseFieldsOk && Array.isArray(candidate.session?.exercises)
}

function readStorage(): ActiveWorkout | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!isStoredWorkout(parsed)) return null
    const { v: _version, ...workout } = parsed
    // Workouts saved before pausing existed have neither field.
    return { ...workout, pausedAt: workout.pausedAt ?? null, pausedMs: workout.pausedMs ?? 0 }
  } catch {
    return null
  }
}

function writeStorage(workout: ActiveWorkout | null) {
  try {
    if (workout) window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ v: 1, ...workout } satisfies StoredWorkout))
    else window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage full or blocked: the workout still lives in memory for this tab.
  }
}

function emit() {
  listeners.forEach((listener) => listener())
}

export function getActiveWorkout() {
  if (!loaded) {
    loaded = true
    current = readStorage()
  }
  return current
}

function set(next: ActiveWorkout | null) {
  current = next
  loaded = true
  writeStorage(next)
  emit()
}

/** Starts (and persists) a workout from a plan, or an empty one when `plan` is null. Replaces any active workout. */
export function beginWorkout(plan: PlannedWorkout | null) {
  set({
    session: initSession(plan),
    startedAt: Date.now(),
    pausedAt: null,
    pausedMs: 0,
    plan: plan ? { highlight: plan.highlight } : null,
  })
}

/** Applies an update to the session (e.g. a reducer step). No-op when no workout is active. */
export function updateActiveSession(update: (session: SessionState) => SessionState) {
  const active = getActiveWorkout()
  if (!active) return
  const session = update(active.session)
  if (session !== active.session) set({ ...active, session })
}

/** Stops the clock and the rest timer until `resumeWorkout`. No-op when nothing is active or it is already paused. */
export function pauseWorkout(now = Date.now()) {
  const active = getActiveWorkout()
  if (active) set(pauseClock(active, now))
}

/** Restarts the clock without the paused time, and pushes a running rest timer back by as much. */
export function resumeWorkout(now = Date.now()) {
  const active = getActiveWorkout()
  if (!active || active.pausedAt === null) return
  const { clock, pausedFor } = resumeClock(active, now)
  const { rest } = active.session
  // A rest that had already run out before the pause stays finished.
  const resting = rest && rest.endsAt > (active.pausedAt ?? 0)
  set({ ...clock, session: resting ? { ...active.session, rest: { ...rest, endsAt: rest.endsAt + pausedFor } } : active.session })
}

export function clearActiveWorkout() {
  set(null)
}

function onStorage(event: StorageEvent) {
  if (event.key !== STORAGE_KEY && event.key !== null) return
  current = readStorage()
  emit()
}

export function subscribeActiveWorkout(listener: () => void) {
  listeners.add(listener)
  if (listeners.size === 1) window.addEventListener("storage", onStorage)
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) window.removeEventListener("storage", onStorage)
  }
}
