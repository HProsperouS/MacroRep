import { format, parseISO } from "date-fns"
import { useMemo } from "react"

import { TargetBarChart } from "@/components/charts/target-bar-chart"
import { QueryError } from "@/components/layout/query-error"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDailyCalories } from "@/hooks/use-progress"
import { formatNumber } from "@/lib/format"
import type { DailyCaloriesResponse, DayStatus } from "@/types/progress"

const DAYS = 7

const DAY_NOTES: Partial<Record<DayStatus, string>> = {
  partial: "Under half the target. Counted as eaten; log anything missed.",
  missing: "Nothing logged: left out of the weekly total.",
  "in-progress": "Today isn’t counted until it ends.",
}

export function CaloriesWeekCard({ className }: { className?: string }) {
  const daily = useDailyCalories(DAYS)

  const chartData = useMemo(
    () =>
      (daily.data?.days ?? []).map((day) => {
        const date = parseISO(day.date)
        return {
          key: day.date,
          label: day.status === "in-progress" ? "Today" : format(date, "EEE"),
          tooltipTitle: format(date, "EEE, d MMM"),
          value: day.calories,
          muted: day.status !== "complete",
          note: DAY_NOTES[day.status],
        }
      }),
    [daily.data],
  )

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Calories · last {DAYS} days</CardTitle>
        <CardAction className="text-xs text-muted-foreground">Dashed line = target</CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {daily.isError ? (
          <QueryError title="Couldn’t load recent calories" error={daily.error} onRetry={() => void daily.refetch()} />
        ) : daily.data ? (
          <>
            <TargetBarChart
              data={chartData}
              target={daily.data.targetCalories}
              seriesLabel="Eaten"
              formatValue={(value) => formatNumber(value)}
              ariaLabel={`Calories eaten over the last ${DAYS} days against a ${formatNumber(daily.data.targetCalories)} kcal target`}
              height={200}
            />
            <WeekGap data={daily.data} />
          </>
        ) : (
          <Skeleton className="h-50 w-full" />
        )}
      </CardContent>
    </Card>
  )
}

/** Total intake vs target over the finished days that were logged. */
function WeekGap({ data }: { data: DailyCaloriesResponse }) {
  const logged = data.days.filter((day) => day.status === "complete" || day.status === "partial")
  if (logged.length === 0) return <p className="text-xs text-muted-foreground">No finished days logged yet this week.</p>

  const partial = logged.filter((day) => day.status === "partial").length
  const gap = data.targetGapKcal
  const days = `${logged.length} logged ${logged.length === 1 ? "day" : "days"}`

  return (
    <p className="text-xs text-muted-foreground">
      {gap === 0 ? (
        <>On target across {days}</>
      ) : (
        <>
          <span className="font-medium text-foreground tabular-nums">{formatNumber(Math.abs(gap))} kcal</span> {gap < 0 ? "under" : "over"} target across {days}
        </>
      )}
      {partial > 0 ? ` · ${partial} under half the target` : null}
    </p>
  )
}
