import { Target, Trophy } from "lucide-react"
import { Link } from "react-router-dom"

import { Stat } from "@/components/layout/stat"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDuration, formatNumber } from "@/lib/format"
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
                    <span className="font-medium">{target.exercise}:</span> {formatNumber(target.weightKg, 1)} kg ×{" "}
                    {target.reps}
                    <span className="block text-muted-foreground">
                      {target.increase
                        ? "Every rep came with room to spare, so go up."
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
