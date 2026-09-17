import { ArrowDown, ArrowUp, Dumbbell, Minus, NotebookText, Plus, Trash2 } from "lucide-react"

import { SET_GRID, SetRow } from "@/components/workout/set-row"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { setLabels, type SessionAction, type SessionExercise } from "@/lib/workout-session"

type ExerciseCardProps = {
  exercise: SessionExercise
  isFirst: boolean
  isLast: boolean
  dispatch: (action: SessionAction) => void
  onRemove: (exercise: SessionExercise) => void
}

export function ExerciseCard({ exercise, isFirst, isLast, dispatch, onRemove }: ExerciseCardProps) {
  const activeSetId = exercise.sets.find((set) => !set.done)?.id
  const doneCount = exercise.sets.filter((set) => set.done).length
  const labels = setLabels(exercise.sets)
  const lastSet = exercise.sets[exercise.sets.length - 1]
  const canRemoveSet = exercise.sets.length > 1 && lastSet !== undefined && !lastSet.done

  return (
    <Card>
      <CardHeader>
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-lg border bg-muted text-muted-foreground" aria-hidden>
            <Dumbbell className="size-5" />
          </span>
          <div className="flex min-w-0 flex-col gap-0.5">
            <CardTitle className="truncate text-base">{exercise.name}</CardTitle>
            <CardDescription className="truncate">
              {exercise.equipment} · {exercise.muscles}
            </CardDescription>
          </div>
        </div>
        <CardAction className="flex items-center gap-2">
          {exercise.tag ? <Badge className="bg-primary/12 text-primary">{exercise.tag}</Badge> : null}
          <span className="text-xs whitespace-nowrap text-muted-foreground">
            {doneCount}/{exercise.sets.length}
          </span>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {exercise.note ? (
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <NotebookText className="mt-0.5 size-4 shrink-0" aria-hidden />
            {exercise.note}
          </p>
        ) : null}

        <div className={cn(SET_GRID, "text-[11px] font-semibold tracking-widest text-muted-foreground uppercase")} aria-hidden>
          <span>Set</span>
          <span>Previous</span>
          <span className="text-center">kg</span>
          <span className="text-center">Reps</span>
          <span />
        </div>

        <ul className="flex flex-col gap-1">
          {exercise.sets.map((set, index) => {
            return (
              <SetRow
                key={set.id}
                exerciseName={exercise.name}
                set={set}
                label={labels[index]}
                active={set.id === activeSetId}
                onEdit={(field, value) => dispatch({ type: "edit", exerciseId: exercise.id, setId: set.id, field, value })}
                onToggle={() => dispatch({ type: "toggle", exerciseId: exercise.id, setId: set.id, now: Date.now() })}
              />
            )
          })}
        </ul>

        <div className="flex items-center gap-1.5">
          <Button variant="ghost" className="h-11 flex-1 border border-dashed" onClick={() => dispatch({ type: "add-set", exerciseId: exercise.id })}>
            <Plus data-icon="inline-start" />
            Add set
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11 text-muted-foreground"
            aria-label={`Remove last set of ${exercise.name}`}
            disabled={!canRemoveSet}
            onClick={() => dispatch({ type: "remove-last-set", exerciseId: exercise.id })}
          >
            <Minus />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11 text-muted-foreground"
            aria-label={`Move ${exercise.name} up`}
            disabled={isFirst}
            onClick={() => dispatch({ type: "move-exercise", exerciseId: exercise.id, direction: -1 })}
          >
            <ArrowUp />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11 text-muted-foreground"
            aria-label={`Move ${exercise.name} down`}
            disabled={isLast}
            onClick={() => dispatch({ type: "move-exercise", exerciseId: exercise.id, direction: 1 })}
          >
            <ArrowDown />
          </Button>
          <Button variant="ghost" size="icon-lg" className="size-11 text-muted-foreground hover:text-destructive" aria-label={`Remove ${exercise.name}`} onClick={() => onRemove(exercise)}>
            <Trash2 />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
