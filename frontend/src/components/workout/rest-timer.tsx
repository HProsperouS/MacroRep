import { Timer } from "lucide-react"
import { useState, type FormEvent } from "react"

import { CalorieRing } from "@/components/charts/calorie-ring"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useNow } from "@/hooks/use-now"
import { formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"
import { parseRestInput, restLabel } from "@/lib/rest-input"
import { MAX_REST_SECONDS, MIN_REST_SECONDS, type RestTimer as RestTimerState, type SessionAction } from "@/lib/workout-session"

const PRESETS = [60, 90, 120, 180]

type RestTimerProps = {
  rest: RestTimerState | null
  /** The rest to highlight: the exercise just worked on's planned rest. */
  suggestedSeconds: number
  dispatch: (action: SessionAction) => void
  className?: string
}

/** Isolated so only this card re-renders every second. Never starts on its own: each rest is
 *  picked when it's needed, since different sets want different rests. */
export function RestTimer({ rest, suggestedSeconds, dispatch, className }: RestTimerProps) {
  if (!rest) return <RestPicker suggestedSeconds={suggestedSeconds} dispatch={dispatch} className={className} />
  return <RunningRest rest={rest} dispatch={dispatch} className={className} />
}

function RestPicker({ suggestedSeconds, dispatch, className }: Omit<RestTimerProps, "rest">) {
  const [custom, setCustom] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const options = [...new Set([...PRESETS, suggestedSeconds])].sort((a, b) => a - b)

  function submitCustom(event: FormEvent) {
    event.preventDefault()
    const seconds = parseRestInput(custom ?? "")
    if (seconds === null) {
      setError(`Enter ${MIN_REST_SECONDS}s to ${MAX_REST_SECONDS / 60}m, like 75 or 2:30`)
      return
    }
    setCustom(null)
    setError(null)
    dispatch({ type: "start-rest", seconds, now: Date.now() })
  }

  return (
    <Card size="sm" className={className}>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Timer className="size-5 shrink-0" aria-hidden />
          <span>Start a rest when you need one</span>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Start rest timer">
          {options.map((seconds) => (
            <Button
              key={seconds}
              variant={seconds === suggestedSeconds ? "default" : "outline"}
              className="h-11 min-w-14 px-3 tabular-nums"
              aria-label={`Rest ${formatDuration(seconds)}${seconds === suggestedSeconds ? " (suggested)" : ""}`}
              onClick={() => dispatch({ type: "start-rest", seconds, now: Date.now() })}
            >
              {restLabel(seconds)}
            </Button>
          ))}
          {custom === null ? (
            <Button variant="ghost" className="h-11 px-3" onClick={() => setCustom("")}>
              Custom
            </Button>
          ) : null}
        </div>
        {custom !== null ? (
          <form className="flex flex-col gap-1" onSubmit={submitCustom} noValidate>
            <div className="flex items-center gap-1.5">
              <Input
                autoFocus
                inputMode="text"
                className="h-11 flex-1"
                placeholder="e.g. 75 or 2:30"
                aria-label="Custom rest"
                aria-invalid={error !== null}
                value={custom}
                onChange={(event) => {
                  setCustom(event.target.value)
                  setError(null)
                }}
              />
              <Button type="submit" className="h-11 px-4">
                Start
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="h-11 px-3"
                onClick={() => {
                  setCustom(null)
                  setError(null)
                }}
              >
                Cancel
              </Button>
            </div>
            {error ? (
              <p className="text-xs text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </form>
        ) : null}
      </CardContent>
    </Card>
  )
}

function RunningRest({ rest, dispatch, className }: { rest: RestTimerState; dispatch: (action: SessionAction) => void; className?: string }) {
  const now = useNow()
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
