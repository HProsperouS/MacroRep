import { Dumbbell, Play, Plus } from "lucide-react"

import { QueryError } from "@/components/layout/query-error"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { PlannedWorkout } from "@/types/workout"

type StartWorkoutProps = {
  plan: PlannedWorkout | null | undefined
  planPending: boolean
  planError: unknown
  onRetryPlan: () => void
  onStartPlan: () => void
  onStartEmpty: () => void
}

/** Choose between today's planned session and an empty workout. */
export function StartWorkout({ plan, planPending, planError, onRetryPlan, onStartPlan, onStartEmpty }: StartWorkoutProps) {
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
    </div>
  )
}
