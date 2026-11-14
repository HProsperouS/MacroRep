import { formatDuration } from "@/lib/format"
import { MAX_REST_SECONDS, MIN_REST_SECONDS } from "@/lib/workout-session"

/** "60s" under two minutes, "2m" or "2:30" beyond. */
export function restLabel(seconds: number) {
  if (seconds < 120) return `${seconds}s`
  return seconds % 60 === 0 ? `${seconds / 60}m` : formatDuration(seconds)
}

/** Seconds from "90", "90s", "2m", "2:30" or "1.5m"; null when it isn't one of those. */
export function parseRestInput(raw: string): number | null {
  const value = raw.trim().toLowerCase()
  let seconds: number
  const clock = /^(\d{1,2}):([0-5]\d)$/.exec(value)
  if (clock) seconds = Number(clock[1]) * 60 + Number(clock[2])
  else if (/^\d+(\.\d+)?m$/.test(value)) seconds = Number(value.slice(0, -1)) * 60
  else if (/^\d+s?$/.test(value)) seconds = Number(value.replace("s", ""))
  else return null
  seconds = Math.round(seconds)
  return seconds >= MIN_REST_SECONDS && seconds <= MAX_REST_SECONDS ? seconds : null
}
