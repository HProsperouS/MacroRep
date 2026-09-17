import { CalorieRing } from "@/components/charts/calorie-ring"
import { MacroBar } from "@/components/charts/macro-bar"
import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatNumber } from "@/lib/format"
import type { Nutrition } from "@/lib/macros"
import type { DailyTargets } from "@/types/food"

type DailySummaryCardProps = {
  totals: Nutrition
  targets: DailyTargets
}

export function DailySummaryCard({ totals, targets }: DailySummaryCardProps) {
  const remaining = targets.calories - totals.calories
  const percent = targets.calories > 0 ? Math.round((totals.calories / targets.calories) * 100) : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Daily nutrition</CardTitle>
        <CardAction>
          {remaining >= 0 ? (
            <Badge variant="secondary">{formatNumber(remaining)} kcal left</Badge>
          ) : (
            <Badge variant="destructive">{formatNumber(-remaining)} kcal over</Badge>
          )}
        </CardAction>
      </CardHeader>
      <CardContent className="flex items-center gap-6">
        <CalorieRing value={totals.calories} max={targets.calories} size={104} className="hidden sm:block">
          <span className="font-display text-2xl leading-none font-semibold">{percent}%</span>
          <span className="mt-1 text-xs text-muted-foreground">of target</span>
        </CalorieRing>
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <p>
            <span className="font-display text-4xl leading-none font-semibold">{formatNumber(totals.calories)}</span>{" "}
            <span className="text-sm text-muted-foreground">/ {formatNumber(targets.calories)} kcal</span>
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:gap-5">
            <MacroBar macro="protein" value={totals.protein} target={targets.protein} />
            <MacroBar macro="carbs" value={totals.carbs} target={targets.carbs} />
            <MacroBar macro="fat" value={totals.fat} target={targets.fat} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function DailySummarySkeleton() {
  return (
    <Card aria-busy="true" aria-label="Loading daily nutrition">
      <CardHeader>
        <Skeleton className="h-4 w-32" />
        <CardAction>
          <Skeleton className="h-5 w-24" />
        </CardAction>
      </CardHeader>
      <CardContent className="flex items-center gap-6">
        <Skeleton className="hidden size-26 rounded-full sm:block" />
        <div className="flex flex-1 flex-col gap-4">
          <Skeleton className="h-9 w-48" />
          <div className="flex flex-col gap-3 sm:flex-row sm:gap-5">
            <Skeleton className="h-8 flex-1" />
            <Skeleton className="h-8 flex-1" />
            <Skeleton className="h-8 flex-1" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
