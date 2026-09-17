import { Timer } from "lucide-react"

import { CalorieRing } from "@/components/charts/calorie-ring"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useNow } from "@/hooks/use-now"
import { formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { RestTimer as RestTimerState, SessionAction } from "@/lib/workout-session"

type RestTimerProps = {
  rest: RestTimerState | null
  dispatch: (action: SessionAction) => void
  className?: string
}

/** Isolated so only this card re-renders every second. */
export function RestTimer({ rest, dispatch, className }: RestTimerProps) {
  const now = useNow()

  if (!rest) {
    return (
      <Card size="sm" className={className}>
        <CardContent className="flex items-center gap-3 text-sm text-muted-foreground">
          <Timer className="size-5 shrink-0" aria-hidden />
          The rest timer starts when you complete a set.
        </CardContent>
      </Card>
    )
  }

  const remaining = Math.max(0, Math.ceil((rest.endsAt - now) / 1000))
  const finished = remaining === 0

  return (
    <Card size="sm" className={cn("bg-primary/5 ring-primary/35", className)}>
      <CardContent className="flex flex-wrap items-center gap-3">
        <CalorieRing value={rest.totalSeconds - remaining} max={rest.totalSeconds} size={48} strokeWidth={5}>
          <Timer className="size-5 text-primary" aria-hidden />
        </CalorieRing>
        <div className="flex min-w-0 flex-1 flex-col gap-1" role="timer" aria-live={finished ? "assertive" : "off"}>
          <span className="text-[11px] font-semibold tracking-widest text-primary uppercase">{finished ? "Rest done" : "Rest"}</span>
          <span className="font-display text-3xl leading-none font-semibold tabular-nums">{finished ? "Next set" : formatDuration(remaining)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" className="h-11 px-3" disabled={finished} onClick={() => dispatch({ type: "adjust-rest", seconds: -15, now: Date.now() })}>
            −15s
          </Button>
          <Button variant="outline" className="h-11 px-3" onClick={() => dispatch({ type: "adjust-rest", seconds: 15, now: Date.now() })}>
            +15s
          </Button>
          <Button variant="ghost" className="h-11 px-3" onClick={() => dispatch({ type: "skip-rest" })}>
            {finished ? "Dismiss" : "Skip"}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
