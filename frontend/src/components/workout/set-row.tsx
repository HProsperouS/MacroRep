import { Check } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"
import { isSetCompletable, parseRpe, type SessionSet } from "@/lib/workout-session"

type SetRowProps = {
  exerciseName: string
  set: SessionSet
  /** "W" for warm-ups, otherwise the working set number. */
  label: string
  active: boolean
  onEdit: (field: "weight" | "reps" | "rpe", value: string) => void
  onToggle: () => void
}

export const SET_GRID = "grid grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_3rem_2.75rem] items-center gap-1.5"

export function SetRow({ exerciseName, set, label, active, onEdit, onToggle }: SetRowProps) {
  const name = `${exerciseName} set ${label}`
  const weightInvalid = set.weight.trim() !== "" && !(Number(set.weight) >= 0)
  const repsInvalid = set.reps.trim() !== "" && !(Number.isInteger(Number(set.reps)) && Number(set.reps) > 0)
  const rpeInvalid = parseRpe(set.rpe) === undefined
  const invalid = !set.done && !isSetCompletable(set)

  return (
    <li
      className={cn(
        SET_GRID,
        "-mx-2 rounded-lg px-2 py-1.5 transition-colors",
        set.done && "bg-primary/7",
        active && "ring-1 ring-primary/45",
      )}
    >
      <span className={cn("font-display text-xl font-semibold", set.kind === "warmup" ? "text-carbs" : "text-foreground")}>
        {label}
        {set.kind === "warmup" ? <span className="sr-only"> (warm-up)</span> : null}
      </span>
      <span className="truncate text-sm text-muted-foreground">
        {set.previous
          ? `${formatNumber(set.previous.weightKg, 1)} × ${set.previous.reps}${set.previous.rpe != null ? ` @${set.previous.rpe}` : ""}`
          : "—"}
      </span>
      <Input
        aria-label={`${name} weight in kg`}
        inputMode="decimal"
        value={set.weight}
        disabled={set.done}
        aria-invalid={weightInvalid || undefined}
        onChange={(event) => onEdit("weight", event.target.value)}
        className="h-11 text-center text-base"
      />
      <Input
        aria-label={`${name} reps`}
        inputMode="numeric"
        value={set.reps}
        disabled={set.done}
        aria-invalid={repsInvalid || undefined}
        onChange={(event) => onEdit("reps", event.target.value)}
        className="h-11 text-center text-base"
      />
      <Input
        aria-label={`${name} RPE, 1 to 10, optional`}
        inputMode="decimal"
        placeholder="RPE"
        value={set.rpe}
        disabled={set.done}
        aria-invalid={rpeInvalid || undefined}
        onChange={(event) => onEdit("rpe", event.target.value)}
        className="h-11 text-center text-base"
      />
      <Button
        variant={set.done ? "default" : "outline"}
        size="icon-lg"
        className="size-11"
        aria-label={set.done ? `Mark ${name} as not done` : `Complete ${name}`}
        aria-pressed={set.done}
        disabled={invalid}
        onClick={onToggle}
      >
        <Check />
      </Button>
    </li>
  )
}
