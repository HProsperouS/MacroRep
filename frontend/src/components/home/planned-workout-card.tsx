import { Dumbbell, Zap } from "lucide-react"
import { Link } from "react-router-dom"

import { QueryError } from "@/components/layout/query-error"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useTodayWorkout } from "@/hooks/use-workout"

const VISIBLE_CHIPS = 3

export function PlannedWorkoutCard() {
  const workout = useTodayWorkout()

  if (workout.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Planned workout</CardTitle>
        </CardHeader>
        <CardContent>
          <QueryError title="Couldn’t load today’s workout" error={workout.error} onRetry={() => void workout.refetch()} />
        </CardContent>
      </Card>
    )
  }

  if (workout.isPending) {
    return (
      <Card aria-busy="true">
        <CardHeader>
          <CardTitle>Planned workout</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Skeleton className="h-13 w-full" />
          <Skeleton className="h-7 w-2/3" />
        </CardContent>
      </Card>
    )
  }

  const plan = workout.data
  if (!plan) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Planned workout</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Rest day — no session planned.</CardContent>
      </Card>
    )
  }

  const setCount = plan.exercises.reduce((sum, exercise) => sum + exercise.sets.length, 0)
  const hidden = plan.exercises.length - VISIBLE_CHIPS

  return (
    <Card>
      <CardHeader>
        <CardTitle>Planned workout</CardTitle>
        <CardAction>
          <Badge variant="outline">{plan.weekLabel}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center gap-3.5">
          <span className="flex size-13 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary" aria-hidden>
            <Dumbbell className="size-6" />
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <span className="truncate text-lg font-semibold">{plan.name}</span>
            <span className="text-sm text-muted-foreground">
              {plan.exercises.length} exercises · {setCount} sets · ~{plan.estimatedMinutes} min
            </span>
          </div>
        </div>
        <ul className="flex flex-wrap gap-1.5" aria-label="Exercises">
          {plan.exercises.slice(0, VISIBLE_CHIPS).map((exercise) => (
            <li key={exercise.id}>
              <Badge variant="secondary">{exercise.name}</Badge>
            </li>
          ))}
          {hidden > 0 ? (
            <li>
              <Badge variant="secondary">+{hidden} more</Badge>
            </li>
          ) : null}
        </ul>
      </CardContent>
      <CardFooter className="lg:hidden">
        <Button className="h-11 w-full" asChild>
          <Link to="/workout?start=plan">
            <Zap data-icon="inline-start" />
            Start workout
          </Link>
        </Button>
      </CardFooter>
    </Card>
  )
}
