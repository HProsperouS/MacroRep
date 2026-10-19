import { Dumbbell, Pencil, Plus } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { RoutineEditor } from "@/components/workout/routine-editor"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useAssignDay, useClearDay, useCreateRoutine, useDeleteRoutine, useRoutines, useUpdateRoutine, useWeekPlan } from "@/hooks/use-workout"
import { WEEKDAY_LABELS, type Routine } from "@/types/workout"

const REST_DAY = ""

/** `null` shows the lists; `{ routineId: null }` is a new routine being written. */
type Editing = { routineId: string | null } | null

export default function WorkoutPlanPage() {
  const navigate = useNavigate()
  const routines = useRoutines()
  const week = useWeekPlan()
  const createRoutine = useCreateRoutine()
  const updateRoutine = useUpdateRoutine()
  const deleteRoutine = useDeleteRoutine()
  const assignDay = useAssignDay()
  const clearDay = useClearDay()
  const [editing, setEditing] = useState<Editing>(null)

  const editedRoutine = editing?.routineId ? routines.data?.find((routine) => routine.id === editing.routineId) : undefined

  if (editing !== null && (editing.routineId === null || editedRoutine)) {
    return (
      <>
        <PageHeader eyebrow="Workout" title={editedRoutine ? `Edit ${editedRoutine.name}` : "New routine"} />
        <RoutineEditor
          routine={editedRoutine ?? null}
          scheduledDays={editedRoutine?.scheduledDays}
          submitting={createRoutine.isPending || updateRoutine.isPending}
          deleting={deleteRoutine.isPending}
          onSave={(input) => {
            const options = {
              onSuccess: () => {
                toast.success(editedRoutine ? "Routine saved" : "Routine created")
                setEditing(null)
              },
              onError: (error: unknown) => toast.error("Couldn’t save this routine", { description: apiErrorMessage(error) }),
            }
            if (editedRoutine) updateRoutine.mutate({ routineId: editedRoutine.id, input }, options)
            else createRoutine.mutate(input, options)
          }}
          onDelete={() => {
            if (!editedRoutine) return
            deleteRoutine.mutate(editedRoutine.id, {
              onSuccess: () => {
                toast.success(`Deleted ${editedRoutine.name}`)
                setEditing(null)
              },
              onError: (error) => toast.error("Couldn’t delete this routine", { description: apiErrorMessage(error) }),
            })
          }}
          onCancel={() => setEditing(null)}
        />
      </>
    )
  }

  function schedule(dayOfWeek: number, routineId: string) {
    const onError = (error: unknown) => toast.error("Couldn’t change this day", { description: apiErrorMessage(error) })
    if (routineId === REST_DAY) clearDay.mutate(dayOfWeek, { onError })
    else assignDay.mutate({ dayOfWeek, routineId }, { onError })
  }

  const scheduling = assignDay.isPending || clearDay.isPending

  return (
    <>
      <PageHeader
        eyebrow="Workout"
        title="Plan"
        actions={
          <Button variant="outline" className="h-10" onClick={() => navigate("/workout")}>
            Back to workout
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Routines</CardTitle>
          <CardDescription>Reusable workouts. Edit one and every day it’s scheduled on follows.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {routines.isError ? (
            <QueryError title="Couldn’t load your routines" error={routines.error} onRetry={() => void routines.refetch()} retrying={routines.isFetching} />
          ) : routines.data ? (
            <>
              {routines.data.length === 0 ? <p className="text-sm text-muted-foreground">No routines yet. Create one, then schedule it below.</p> : null}
              {routines.data.map((routine) => (
                <RoutineRow key={routine.id} routine={routine} onEdit={() => setEditing({ routineId: routine.id })} />
              ))}
              <Button variant="outline" className="h-11 w-full border-dashed" onClick={() => setEditing({ routineId: null })}>
                <Plus data-icon="inline-start" />
                New routine
              </Button>
            </>
          ) : (
            <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading routines">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Week schedule</CardTitle>
          <CardDescription>Pick a routine for each day, or leave it as a rest day.</CardDescription>
        </CardHeader>
        <CardContent>
          {week.isError ? (
            <QueryError title="Couldn’t load your week" error={week.error} onRetry={() => void week.refetch()} retrying={week.isFetching} />
          ) : week.data && routines.data ? (
            <ul className="flex flex-col gap-2">
              {week.data.map((day) => (
                <li key={day.dayOfWeek} className="flex items-center justify-between gap-3">
                  <label htmlFor={`schedule-${day.dayOfWeek}`} className="text-sm font-medium">
                    {WEEKDAY_LABELS[day.dayOfWeek]}
                  </label>
                  <select
                    id={`schedule-${day.dayOfWeek}`}
                    value={day.plan?.id ?? REST_DAY}
                    disabled={scheduling}
                    onChange={(event) => schedule(day.dayOfWeek, event.target.value)}
                    className="h-10 w-48 max-w-[60%] rounded-md border bg-background px-2 text-sm"
                  >
                    <option value={REST_DAY}>Rest day</option>
                    {routines.data.map((routine) => (
                      <option key={routine.id} value={routine.id}>
                        {routine.name}
                      </option>
                    ))}
                  </select>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading schedule">
              {Array.from({ length: 7 }, (_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  )
}

function RoutineRow({ routine, onEdit }: { routine: Routine; onEdit: () => void }) {
  const days = routine.scheduledDays.map((day) => WEEKDAY_LABELS[day].slice(0, 3)).join(", ")
  const count = routine.exercises.length
  return (
    <div className="flex items-center gap-3 rounded-lg border px-3 py-2">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground" aria-hidden>
        <Dumbbell className="size-5" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-sm font-medium">{routine.name}</span>
        <span className="truncate text-sm text-muted-foreground">
          {count} exercise{count === 1 ? "" : "s"} · {days || "Not scheduled"}
        </span>
      </div>
      <Button variant="ghost" className="h-10" onClick={onEdit} aria-label={`Edit ${routine.name}`}>
        <Pencil data-icon="inline-start" />
        Edit
      </Button>
    </div>
  )
}
