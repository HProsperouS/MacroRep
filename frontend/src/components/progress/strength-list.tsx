import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatNumber, formatSigned } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { StrengthLift } from "@/types/progress"

export function StrengthList({ lifts, className }: { lifts: StrengthLift[]; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Strength (est. 1RM, kg)</CardTitle>
      </CardHeader>
      <CardContent>
        {lifts.length === 0 ? (
          <p className="text-sm text-muted-foreground">Log a few working sets to see estimated one-rep maxes.</p>
        ) : (
          <ul className="divide-y">
            {lifts.map((lift) => (
              <li key={lift.exercise} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                <span className="truncate text-sm">{lift.exercise}</span>
                <span className="flex shrink-0 items-baseline gap-3">
                  <span className="font-display text-2xl leading-none font-semibold">{formatNumber(lift.estimated1RmKg, 1)}</span>
                  <span className={cn("w-12 text-right text-sm tabular-nums", lift.changeKg >= 0 ? "text-primary" : "text-destructive")}>
                    {formatSigned(lift.changeKg)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
