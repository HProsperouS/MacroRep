import { format, isToday, parseISO } from "date-fns"
import { useMemo } from "react"

import { TargetBarChart } from "@/components/charts/target-bar-chart"
import { QueryError } from "@/components/layout/query-error"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useNutritionTargets } from "@/hooks/use-food-log"
import { useDailyCalories } from "@/hooks/use-progress"
import { formatNumber } from "@/lib/format"

const DAYS = 7

export function CaloriesWeekCard({ className }: { className?: string }) {
  const daily = useDailyCalories(DAYS)
  const targets = useNutritionTargets()

  const chartData = useMemo(
    () =>
      (daily.data ?? []).map((day) => {
        const date = parseISO(day.date)
        return { key: day.date, label: isToday(date) ? "Today" : format(date, "EEE"), tooltipTitle: format(date, "EEE, d MMM"), value: day.calories }
      }),
    [daily.data],
  )

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Calories · last {DAYS} days</CardTitle>
        <CardAction className="text-xs text-muted-foreground">Dashed line = target</CardAction>
      </CardHeader>
      <CardContent>
        {daily.isError ? (
          <QueryError title="Couldn’t load recent calories" error={daily.error} onRetry={() => void daily.refetch()} />
        ) : daily.data && targets.data ? (
          <TargetBarChart
            data={chartData}
            target={targets.data.calories}
            seriesLabel="Eaten"
            formatValue={(value) => formatNumber(value)}
            ariaLabel={`Calories eaten over the last ${DAYS} days against a ${formatNumber(targets.data.calories)} kcal target`}
            height={200}
          />
        ) : (
          <Skeleton className="h-50 w-full" />
        )}
      </CardContent>
    </Card>
  )
}
