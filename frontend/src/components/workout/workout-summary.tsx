import { Target, Trophy } from "lucide-react"
import { Link } from "react-router-dom"

import { Stat } from "@/components/layout/stat"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ExerciseSets } from "@/components/workout/exercise-sets"
import { formatDuration, formatNumber } from "@/lib/format"
import { bodyWeightNote } from "@/lib/load-labels"
import type { WorkoutSummary as WorkoutSummaryData } from "@/types/workout"

export function WorkoutSummary({ summary }: { summary: WorkoutSummaryData }) {
  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <CardTitle className="text-lg">Workout saved</CardTitle>
        <CardDescription>{summary.name}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Duration" value={formatDuration(summary.durationSeconds)} />
          <Stat label="Sets" value={summary.setsCompleted} />
          <Stat label="Volume" value={formatNumber(summary.volumeKg)} unit="kg" />
        </div>
        {summary.repBasedReps || bodyWeightNote(summary.bodyWeightKg, summary.exercises) ? (
          <p className="-mt-2 text-sm text-muted-foreground">
            {[summary.repBasedReps ? `Plus ${formatNumber(summary.repBasedReps)} band reps` : null, bodyWeightNote(summary.bodyWeightKg, summary.exercises)]
              .filter(Boolean)
              .join(". ")}
          </p>
        ) : null}
        {summary.personalRecords.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {summary.personalRecords.map((record) => (
              <li key={record} className="flex items-center gap-2 text-sm">
                <Trophy className="size-4 text-primary" aria-hidden />
                {record}
                <Badge className="bg-primary/12 text-primary">PR</Badge>
              </li>
            ))}
          </ul>
        ) : null}
        {summary.exercises && summary.exercises.length > 0 ? (
          <section aria-labelledby="done-heading" className="flex flex-col gap-3">
            <h3 id="done-heading" className="text-sm font-medium">
              What you did
            </h3>
            <div className="flex flex-col gap-4 rounded-lg border bg-muted/30 px-3 py-2">
              {summary.exercises.map((exercise, index) => (
                <ExerciseSets key={`${index}-${exercise.name}`} exercise={exercise} compact />
              ))}
            </div>
          </section>
        ) : null}
        {summary.nextTargets.length > 0 ? (
          <section aria-labelledby="next-time-heading" className="flex flex-col gap-2">
            <h3 id="next-time-heading" className="text-sm font-medium">
              Next time
            </h3>
            <ul className="flex flex-col gap-2">
              {summary.nextTargets.map((target) => (
                <li key={target.exercise} className="flex items-start gap-2 text-sm">
                  <Target className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                  <span>
                    {/* No weight on the bar (a band, or bodyweight alone) progresses by reps. */}
                    <span className="font-medium">{target.exercise}:</span>{" "}
                    {target.weightKg > 0 ? `${formatNumber(target.weightKg, 1)} kg × ${target.reps}` : `${target.reps} reps`}
                    <span className="block text-muted-foreground">
                      {target.increase
                        ? target.weightKg > 0
                          ? "Every rep came with room to spare, so go up."
                          : "Every rep came with room to spare, so aim for one more."
                        : "Stay here until every rep feels comfortable."}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </CardContent>
      <CardFooter className="flex flex-col-reverse gap-2 border-t sm:flex-row sm:justify-end">
        <Button variant="outline" className="h-10 w-full sm:w-auto" asChild>
          <Link to="/progress">View progress</Link>
        </Button>
        <Button className="h-10 w-full sm:w-auto" asChild>
          <Link to="/">Back to home</Link>
        </Button>
      </CardFooter>
    </Card>
  )
}
