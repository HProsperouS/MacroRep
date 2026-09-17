import { CalorieRing } from "@/components/charts/calorie-ring"
import { MacroBar } from "@/components/charts/macro-bar"
import { Badge } from "@/components/ui/badge"
import { formatNumber } from "@/lib/format"
import type { Nutrition } from "@/lib/macros"
import { cn } from "@/lib/utils"
import type { DailyTargets } from "@/types/food"

type DailySummaryCardProps = {
  totals: Nutrition
  targets: DailyTargets
}

export function DailySummaryCard({ totals, targets }: DailySummaryCardProps) {
  const remaining = targets.calories - totals.calories
  const percent = targets.calories > 0 ? Math.round((totals.calories / targets.calories) * 100) : 0

  return (
    <section aria-label="Daily nutrition" className="flex items-center gap-7 rounded-2xl border bg-card p-4 sm:p-5">
      <CalorieRing value={totals.calories} max={targets.calories} size={112} className="hidden sm:block">
        <span className="font-display text-3xl leading-none font-semibold">{percent}%</span>
        <span className="mt-1 text-[11px] text-muted-foreground">of target</span>
      </CalorieRing>

      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2">
          <p>
            <span className="font-display text-4xl leading-none font-semibold">{formatNumber(totals.calories)}</span>{" "}
            <span className="text-sm text-muted-foreground">/ {formatNumber(targets.calories)} kcal</span>
          </p>
          <Badge
            variant="outline"
            className={cn(
              "h-6 px-2.5",
              remaining >= 0 ? "border-primary/35 bg-primary/10 text-primary" : "border-destructive/40 bg-destructive/10 text-destructive",
            )}
          >
            {remaining >= 0 ? `${formatNumber(remaining)} kcal left` : `${formatNumber(-remaining)} kcal over`}
          </Badge>
        </div>

        <div className="h-2 overflow-hidden rounded-full bg-border sm:hidden" aria-hidden>
          <div className="h-full rounded-full bg-calories" style={{ width: `${Math.min(percent, 100)}%` }} />
        </div>

        <div className="flex gap-4 sm:gap-5">
          <MacroBar macro="protein" value={totals.protein} target={targets.protein} />
          <MacroBar macro="carbs" value={totals.carbs} target={targets.carbs} />
          <MacroBar macro="fat" value={totals.fat} target={targets.fat} />
        </div>
      </div>
    </section>
  )
}
