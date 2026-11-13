import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatNumber, formatSigned } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { RepLift, StrengthLift } from "@/types/progress"

type StrengthListProps = {
  lifts: StrengthLift[]
  /** Band exercises: no load to estimate a 1RM from, so their best set in reps. */
  repLifts?: RepLift[]
  className?: string
}

export function StrengthList({ lifts, repLifts = [], className }: StrengthListProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Strength (est. 1RM, kg)</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {lifts.length === 0 && repLifts.length === 0 ? (
          <p className="text-sm text-muted-foreground">Log a few working sets to see estimated one-rep maxes.</p>
        ) : null}
        {lifts.length > 0 ? (
          <ul className="divide-y">
            {lifts.map((lift) => (
              <StrengthRow key={lift.exercise} exercise={lift.exercise} value={formatNumber(lift.estimated1RmKg, 1)} change={lift.changeKg} changeLabel={formatSigned(lift.changeKg)} />
            ))}
          </ul>
        ) : null}
        {repLifts.length > 0 ? (
          <section aria-labelledby="rep-lifts-heading" className="flex flex-col gap-1">
            <h3 id="rep-lifts-heading" className="text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">
              Best set, reps (bands)
            </h3>
            <ul className="divide-y">
              {repLifts.map((lift) => (
                <StrengthRow
                  key={lift.exercise}
                  exercise={lift.exercise}
                  value={String(lift.bestReps)}
                  unit="reps"
                  change={lift.changeReps}
                  changeLabel={lift.changeReps > 0 ? `+${lift.changeReps}` : String(lift.changeReps)}
                />
              ))}
            </ul>
          </section>
        ) : null}
      </CardContent>
    </Card>
  )
}

function StrengthRow({ exercise, value, unit, change, changeLabel }: { exercise: string; value: string; unit?: string; change: number; changeLabel: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
      <span className="truncate text-sm">{exercise}</span>
      <span className="flex shrink-0 items-baseline gap-3">
        <span className="font-display text-2xl leading-none font-semibold">
          {value}
          {unit ? <span className="ml-1 font-sans text-sm font-normal text-muted-foreground">{unit}</span> : null}
        </span>
        <span className={cn("w-12 text-right text-sm tabular-nums", change >= 0 ? "text-primary" : "text-destructive")}>{changeLabel}</span>
      </span>
    </li>
  )
}
