import { ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"

import { CalorieRing } from "@/components/charts/calorie-ring"
import { MacroBar } from "@/components/charts/macro-bar"
import { QueryError } from "@/components/layout/query-error"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useFoodLog, useNutritionTargets } from "@/hooks/use-food-log"
import { EMPTY_ENTRIES, groupEntries } from "@/lib/food-log"
import { formatNumber } from "@/lib/format"

type TodayNutritionCardProps = {
  today: Date
  /** Estimated expenditure from the progress endpoint; hidden when unknown. */
  expenditureKcal?: number
}

export function TodayNutritionCard({ today, expenditureKcal }: TodayNutritionCardProps) {
  const foodLog = useFoodLog(today)
  const targets = useNutritionTargets()

  const header = (
    <CardHeader>
      <CardTitle>Today’s nutrition</CardTitle>
      <CardAction>
        <Button variant="link" size="sm" className="px-0" asChild>
          <Link to="/food">
            Log food
            <ChevronRight data-icon="inline-end" />
          </Link>
        </Button>
      </CardAction>
    </CardHeader>
  )

  if (foodLog.isError || targets.isError) {
    return (
      <Card>
        {header}
        <CardContent>
          <QueryError
            title="Couldn’t load today’s nutrition"
            error={foodLog.error ?? targets.error}
            onRetry={() => {
              void foodLog.refetch()
              void targets.refetch()
            }}
          />
        </CardContent>
      </Card>
    )
  }

  if (!foodLog.data || !targets.data) {
    return (
      <Card aria-busy="true">
        {header}
        <CardContent className="flex flex-col gap-5">
          <div className="flex items-center gap-5">
            <Skeleton className="size-33 rounded-full" />
            <div className="flex flex-1 flex-col gap-3">
              <Skeleton className="h-8 w-40" />
              <Skeleton className="h-8 w-32" />
            </div>
          </div>
          <Skeleton className="h-8 w-full" />
        </CardContent>
      </Card>
    )
  }

  const { totals } = groupEntries(foodLog.data.entries ?? EMPTY_ENTRIES)
  const target = targets.data
  const remaining = target.calories - totals.calories

  return (
    <Card>
      {header}
      <CardContent className="flex flex-col gap-5">
        <div className="flex items-center gap-5">
          <CalorieRing value={totals.calories} max={target.calories}>
            <span className="font-display text-4xl leading-none font-semibold">{formatNumber(Math.abs(remaining))}</span>
            <span className="mt-1 text-xs text-muted-foreground">{remaining >= 0 ? "kcal left" : "kcal over"}</span>
          </CalorieRing>
          <dl className="flex min-w-0 flex-1 flex-col gap-3.5">
            <div className="flex flex-col gap-0.5">
              <dt className="text-xs text-muted-foreground">Eaten</dt>
              <dd>
                <span className="font-display text-3xl leading-none font-semibold">{formatNumber(totals.calories)}</span>{" "}
                <span className="text-sm text-muted-foreground">/ {formatNumber(target.calories)} kcal</span>
              </dd>
            </div>
            {expenditureKcal ? (
              <div className="flex flex-col gap-0.5">
                <dt className="text-xs text-muted-foreground">Burned (est. expenditure)</dt>
                <dd>
                  <span className="font-display text-3xl leading-none font-semibold">{formatNumber(expenditureKcal)}</span>{" "}
                  <span className="text-sm text-muted-foreground">kcal / day</span>
                </dd>
              </div>
            ) : null}
          </dl>
        </div>
        <div className="flex flex-col gap-3.5 sm:flex-row sm:gap-5">
          <MacroBar macro="protein" value={totals.protein} target={target.protein} />
          <MacroBar macro="carbs" value={totals.carbs} target={target.carbs} />
          <MacroBar macro="fat" value={totals.fat} target={target.fat} />
        </div>
      </CardContent>
    </Card>
  )
}
