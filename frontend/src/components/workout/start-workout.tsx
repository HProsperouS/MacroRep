import { Dumbbell, Play, Plus } from "lucide-react"

import { QueryError } from "@/components/layout/query-error"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { WEEKDAY_LABELS, type PlannedWorkout, type Routine } from "@/types/workout"

type StartWorkoutProps = {
  plan: PlannedWorkout | null | undefined
  planPending: boolean
  planError: unknown
  onRetryPlan: () => void
  onStartPlan: () => void
  onStartEmpty: () => void
  /** The user's routines, to start any of them today. Not shown until loaded. */
  routines?: Routine[]
  onStartRoutine: (routine: Routine) => void
}

/** Choose between today's planned session, one of your routines, and an empty workout. */
export function StartWorkout({ plan, planPending, planError, onRetryPlan, onStartPlan, onStartEmpty, routines, onStartRoutine }: StartWorkoutProps) {
  const setCount = plan ? plan.exercises.reduce((sum, exercise) => sum + exercise.sets.length, 0) : 0

  return (
    <div className="grid items-start gap-4 lg:grid-cols-2 lg:gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Today’s plan</CardTitle>
          {plan ? <CardDescription>{plan.name}</CardDescription> : null}
          {plan ? (
            <CardAction>
              <Badge variant="outline">{plan.weekLabel}</Badge>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent>
          {planError ? (
            <QueryError title="Couldn’t load today’s plan" error={planError} onRetry={onRetryPlan} />
          ) : planPending ? (
            <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading plan">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ) : plan ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                {plan.exercises.length} exercises · {setCount} sets · ~{plan.estimatedMinutes} min
              </p>
              <ol className="flex flex-col gap-1.5 text-sm">
                {plan.exercises.map((exercise, index) => (
                  <li key={exercise.id} className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="w-4 text-right text-xs text-muted-foreground tabular-nums">{index + 1}</span>
                      <span className="truncate">{exercise.name}</span>
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">{exercise.sets.length} sets</span>
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Rest day — nothing is planned. You can still log an empty workout.</p>
          )}
        </CardContent>
        {plan ? (
          <CardFooter>
            <Button className="h-11 w-full" onClick={onStartPlan}>
              <Play data-icon="inline-start" />
              Start planned workout
            </Button>
          </CardFooter>
        ) : null}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Empty workout</CardTitle>
          <CardDescription>Pick exercises as you go. Previous numbers fill in from your last session.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-3 text-sm text-muted-foreground">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-lg border bg-muted" aria-hidden>
            <Dumbbell className="size-5" />
          </span>
          Good for extra sessions, travel gyms, or when you want to change the plan today.
        </CardContent>
        <CardFooter>
          <Button variant={plan ? "outline" : "default"} className="h-11 w-full" onClick={onStartEmpty}>
            <Plus data-icon="inline-start" />
            Start empty workout
          </Button>
        </CardFooter>
      </Card>

      {routines && routines.length > 0 ? (
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Your routines</CardTitle>
            <CardDescription>Start any routine today, whatever day it’s scheduled on.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col divide-y">
              {routines.map((routine) => (
                <li key={routine.id} className="flex items-center gap-3 py-2">
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-sm font-medium">{routine.name}</span>
                    <span className="truncate text-sm text-muted-foreground">
                      {routine.exercises.length} exercise{routine.exercises.length === 1 ? "" : "s"}
                      {routine.scheduledDays.length > 0 ? ` · ${routine.scheduledDays.map((day) => WEEKDAY_LABELS[day].slice(0, 3)).join(", ")}` : ""}
                    </span>
                  </div>
                  <Button variant="outline" className="h-10" onClick={() => onStartRoutine(routine)} aria-label={`Start ${routine.name}`}>
                    <Play data-icon="inline-start" />
                    Start
                  </Button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
