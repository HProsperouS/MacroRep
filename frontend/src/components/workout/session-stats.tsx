import { Clock } from "lucide-react"

import { useNow } from "@/hooks/use-now"
import { formatDuration, formatNumber } from "@/lib/format"
import { elapsedMs, type WorkoutClock } from "@/lib/workout-clock"

/** Time spent training (frozen while paused); isolated because it ticks every second. */
export function SessionClock({ clock }: { clock: WorkoutClock }) {
  const now = useNow()
  return <span className="tabular-nums">{formatDuration(elapsedMs(clock, now) / 1000)}</span>
}

type SessionStatsLineProps = {
  clock: WorkoutClock
  done: number
  total: number
  volumeKg: number
}

export function SessionStatsLine({ clock, done, total, volumeKg }: SessionStatsLineProps) {
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
      <span className="flex items-center gap-1">
        <Clock className="size-3.5" aria-hidden />
        <span className="sr-only">Elapsed</span>
        <SessionClock clock={clock} />
      </span>
      <span>
        {done} / {total} sets
      </span>
      <span>{formatNumber(volumeKg)} kg volume</span>
    </p>
  )
}
