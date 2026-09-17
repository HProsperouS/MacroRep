import { Stat } from "@/components/layout/stat"
import { SessionClock } from "@/components/workout/session-stats"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { formatNumber, formatSigned } from "@/lib/format"
import type { SessionExercise } from "@/lib/workout-session"
import type { StrengthHighlight } from "@/types/workout"

type SessionOverviewProps = {
  startedAt: number
  exercises: SessionExercise[]
  totals: { done: number; total: number; volumeKg: number }
}

/** Desktop sidebar: time, sets, volume and per-exercise progress. */
export function SessionOverview({ startedAt, exercises, totals }: SessionOverviewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Session</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Duration" value={<SessionClock startedAt={startedAt} />} />
          <Stat label="Sets" value={`${totals.done}/${totals.total}`} />
          <Stat label="Volume" value={formatNumber(totals.volumeKg)} unit="kg" />
        </div>
        <Progress value={totals.total > 0 ? (totals.done / totals.total) * 100 : 0} aria-label="Sets completed" />
        <Separator />
        <ul className="flex flex-col gap-2.5 text-sm">
          {exercises.map((exercise) => {
            const done = exercise.sets.filter((set) => set.done).length
            const complete = done === exercise.sets.length
            return (
              <li key={exercise.id} className="flex items-center justify-between gap-3">
                <span className={complete ? "truncate text-muted-foreground line-through" : "truncate"}>{exercise.name}</span>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  {done} / {exercise.sets.length}
                </span>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

export function StrengthHighlightCard({ highlight }: { highlight: StrengthHighlight }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{highlight.exercise} · est. 1RM</CardTitle>
        <CardDescription>
          {formatSigned(highlight.changeKg)} kg over {highlight.periodLabel}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        <span className="flex items-baseline gap-1.5">
          <span className="font-display text-4xl leading-none font-semibold">{formatNumber(highlight.estimated1RmKg, 1)}</span>
          <span className="text-sm text-muted-foreground">kg</span>
        </span>
        <span className="text-xs text-muted-foreground">Best set: {highlight.bestSet}</span>
      </CardContent>
    </Card>
  )
}
