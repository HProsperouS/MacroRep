import { Clock } from "lucide-react"

import { useNow } from "@/hooks/use-now"
import { formatDuration, formatNumber } from "@/lib/format"

/** Elapsed time; isolated because it ticks every second. */
export function SessionClock({ startedAt }: { startedAt: number }) {
  const now = useNow()
  return <span className="tabular-nums">{formatDuration((now - startedAt) / 1000)}</span>
}

type SessionStatsLineProps = {
  startedAt: number
  done: number
  total: number
  volumeKg: number
}

export function SessionStatsLine({ startedAt, done, total, volumeKg }: SessionStatsLineProps) {
  return (
    <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
      <span className="flex items-center gap-1">
        <Clock className="size-3.5" aria-hidden />
        <span className="sr-only">Elapsed</span>
        <SessionClock startedAt={startedAt} />
      </span>
      <span>
        {done} / {total} sets
      </span>
      <span>{formatNumber(volumeKg)} kg volume</span>
    </p>
  )
}
