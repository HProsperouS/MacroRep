import { format, parseISO } from "date-fns"
import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { CheckInHistoryItem, CheckInOutcome } from "@/types/progress"

const OUTCOME: Record<CheckInOutcome, { label: string; variant: "secondary" | "outline" | "destructive"; className?: string }> = {
  applied: { label: "Applied", variant: "secondary", className: "bg-primary/12 text-primary" },
  edited: { label: "Edited", variant: "secondary" },
  rejected: { label: "Rejected", variant: "destructive" },
  "no-changes": { label: "No changes", variant: "outline" },
}

export function CheckInHistory({ items, className }: { items: CheckInHistoryItem[]; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Check-in history</CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/coach">Open coach</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No check-ins in this period.</p>
        ) : (
          <ul className="divide-y">
            {items.map((item) => {
              const outcome = OUTCOME[item.outcome]
              return (
                <li key={item.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-sm font-medium">
                      {item.weekLabel} · {format(parseISO(item.date), "d MMM")}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">{item.summary}</span>
                  </div>
                  <Badge variant={outcome.variant} className={outcome.className}>
                    {outcome.label}
                  </Badge>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
