import { format, parseISO } from "date-fns"
import { ChevronDown } from "lucide-react"
import { useState } from "react"

import { QueryError } from "@/components/layout/query-error"
import { Skeleton } from "@/components/ui/skeleton"
import { useWorkoutDetail } from "@/hooks/use-workout"
import { formatDuration, formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { HistoryExercise, WorkoutHistoryItem } from "@/types/workout"

export function HistoryRow({ workout }: { workout: WorkoutHistoryItem }) {
  const [open, setOpen] = useState(false)
  const detail = useWorkoutDetail(workout.id, open)
  const startedAt = parseISO(workout.startedAt)
  const panelId = `workout-${workout.id}`

  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/50"
      >
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="truncate font-medium">{workout.name}</span>
          <span className="truncate text-sm text-muted-foreground">
            {format(startedAt, "EEE d MMM, HH:mm")} · {formatDuration(workout.durationSeconds)}
          </span>
          <span className="truncate text-sm text-muted-foreground">
            {workout.exerciseCount} exercise{workout.exerciseCount === 1 ? "" : "s"} · {workout.setsCompleted} sets · {formatNumber(workout.volumeKg)} kg
          </span>
        </span>
        <ChevronDown className={cn("size-5 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open ? (
        <div id={panelId} className="border-t bg-muted/30 px-4 py-3">
          {detail.isError ? (
            <QueryError title="Couldn’t load this workout" error={detail.error} onRetry={() => void detail.refetch()} retrying={detail.isFetching} />
          ) : detail.data ? (
            <div className="flex flex-col gap-4">
              {detail.data.exercises.map((exercise, index) => (
                <ExerciseSets key={`${index}-${exercise.name}`} exercise={exercise} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading workout">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
        </div>
      ) : null}
    </li>
  )
}

function ExerciseSets({ exercise }: { exercise: HistoryExercise }) {
  // Warm-ups aren't numbered, so "Set 1" is always the first working set.
  const labels = exercise.sets.map((set, index) =>
    set.kind === "warmup" ? "Warm-up" : `Set ${exercise.sets.slice(0, index + 1).filter((earlier) => earlier.kind === "working").length}`,
  )
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">{exercise.name}</h3>
      <ul className="divide-y">
        {exercise.sets.map((set, index) => (
          <li key={index} className="flex items-center gap-3 py-1.5 text-sm">
            <span className="w-16 shrink-0 text-muted-foreground">{labels[index]}</span>
            <span className="flex-1 tabular-nums">
              {formatNumber(set.weightKg, 2)} kg × {set.reps}
            </span>
            {set.rpe != null ? <span className="shrink-0 text-muted-foreground tabular-nums">RPE {formatNumber(set.rpe, 1)}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
