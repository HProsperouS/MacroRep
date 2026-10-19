import { format, parseISO } from "date-fns"
import { ChevronDown, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { QueryError } from "@/components/layout/query-error"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { WorkoutEditForm } from "@/components/workout/workout-edit-form"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { useDeleteWorkout, useUpdateWorkout, useWorkoutDetail } from "@/hooks/use-workout"
import { formatDuration, formatNumber } from "@/lib/format"
import { toEditable } from "@/lib/workout-edit"
import { historySetLabels } from "@/lib/workout-session"
import { cn } from "@/lib/utils"
import type { HistoryExercise, UpdateWorkoutInput, WorkoutHistoryItem } from "@/types/workout"

export function HistoryRow({ workout }: { workout: WorkoutHistoryItem }) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<OverlayLayout | null>(null)
  const detail = useWorkoutDetail(workout.id, open)
  const update = useUpdateWorkout()
  const remove = useDeleteWorkout()
  const editable = detail.data ? toEditable(detail.data) : null

  function save(input: UpdateWorkoutInput) {
    update.mutate(
      { sessionId: workout.id, input },
      {
        onSuccess: () => {
          setEditing(false)
          toast.success("Workout updated")
        },
        onError: (error) => toast.error("Couldn’t update that workout", { description: apiErrorMessage(error) }),
      },
    )
  }

  function deleteWorkout() {
    remove.mutate(workout.id, {
      onSuccess: () => {
        setConfirmDelete(null)
        toast("Workout deleted", { description: workout.name })
      },
      onError: (error) => toast.error("Couldn’t delete that workout", { description: apiErrorMessage(error) }),
    })
  }
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
          ) : detail.data && editing && editable ? (
            <WorkoutEditForm initial={editable} saving={update.isPending} onSave={save} onCancel={() => setEditing(false)} />
          ) : detail.data ? (
            <div className="flex flex-col gap-4">
              {detail.data.exercises.map((exercise, index) => (
                <ExerciseSets key={`${index}-${exercise.name}`} exercise={exercise} />
              ))}
              <div className="flex justify-end gap-2">
                <Button variant="outline" className="h-10" disabled={!editable} onClick={() => setEditing(true)}>
                  <Pencil data-icon="inline-start" />
                  Edit
                </Button>
                <Button variant="outline" className="h-10 text-destructive" onClick={() => setConfirmDelete(isDesktop ? "dialog" : "drawer")}>
                  <Trash2 data-icon="inline-start" />
                  Delete
                </Button>
              </div>
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

      <ResponsiveOverlay
        open={confirmDelete !== null}
        onOpenChange={(next) => (next ? undefined : setConfirmDelete(null))}
        layout={confirmDelete ?? "dialog"}
        title="Delete this workout?"
        description={`“${workout.name}” and its sets will be removed from your history and progress. This can’t be undone.`}
      >
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" className="h-10" onClick={() => setConfirmDelete(null)} disabled={remove.isPending}>
            Cancel
          </Button>
          <Button variant="destructive" className="h-10" onClick={deleteWorkout} disabled={remove.isPending}>
            {remove.isPending ? <Spinner data-icon="inline-start" /> : null}
            Delete workout
          </Button>
        </div>
      </ResponsiveOverlay>
    </li>
  )
}

function ExerciseSets({ exercise }: { exercise: HistoryExercise }) {
  // Only working sets are numbered, so "Set 1" is always the first working set.
  const labels = historySetLabels(exercise.sets)
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">{exercise.name}</h3>
      <ul className="divide-y">
        {exercise.sets.map((set, index) => (
          <li key={index} className="flex items-center gap-3 py-1.5 text-sm">
            <span className="w-20 shrink-0 text-muted-foreground">{labels[index]}</span>
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
