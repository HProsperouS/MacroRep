import { format, parseISO } from "date-fns"
import { CircleCheck } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ExerciseSets } from "@/components/workout/exercise-sets"
import { useWorkoutDetail, useWorkoutHistory } from "@/hooks/use-workout"
import { formatDuration, formatNumber } from "@/lib/format"
import { rangeFor } from "@/lib/history-range"
import type { WorkoutHistoryItem } from "@/types/workout"

/** What was logged today. Shows nothing until there is something, so a fresh day stays quiet. */
export function DoneTodayCard() {
  const [today] = useState(() => new Date())
  const history = useWorkoutHistory(rangeFor("today", today))
  const workouts = history.data?.pages.flat() ?? []
  if (workouts.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CircleCheck className="size-5 text-primary" aria-hidden />
          Done today
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {workouts.map((workout) => (
          <DoneWorkout key={workout.id} workout={workout} />
        ))}
      </CardContent>
      <CardFooter className="border-t">
        <Button variant="outline" className="h-10 w-full sm:w-auto" asChild>
          <Link to="/workout/history?range=today">View in history</Link>
        </Button>
      </CardFooter>
    </Card>
  )
}

function DoneWorkout({ workout }: { workout: WorkoutHistoryItem }) {
  const detail = useWorkoutDetail(workout.id, true)
  return (
    <section aria-label={workout.name} className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <span className="font-medium">{workout.name}</span>
        <CardDescription>
          {format(parseISO(workout.startedAt), "HH:mm")} · {formatDuration(workout.durationSeconds)} · {workout.setsCompleted} sets · {formatNumber(workout.volumeKg)} kg
        </CardDescription>
      </div>
      {detail.data ? (
        <div className="flex flex-col gap-3">
          {detail.data.exercises.map((exercise, index) => (
            <ExerciseSets key={`${index}-${exercise.name}`} exercise={exercise} compact />
          ))}
        </div>
      ) : detail.isError ? (
        <p className="text-sm text-muted-foreground">Couldn’t load the sets. Open it in history to see them.</p>
      ) : (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading sets">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-8 w-full" />
        </div>
      )}
    </section>
  )
}
