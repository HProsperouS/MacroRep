import { Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { isEditableSetValid, isWorkoutNameValid, toUpdateInput, type EditableSet, type EditableWorkout } from "@/lib/workout-edit"
import { historySetLabels } from "@/lib/workout-session"
import { SET_KIND_LABELS, SET_KINDS, type SetKind, type UpdateWorkoutInput } from "@/types/workout"

type WorkoutEditFormProps = {
  initial: EditableWorkout
  saving: boolean
  onSave: (input: UpdateWorkoutInput) => void
  onCancel: () => void
}

/** Corrects a finished workout in place: its name, and each set's type, weight, reps and RPE, or drops a set. */
export function WorkoutEditForm({ initial, saving, onSave, onCancel }: WorkoutEditFormProps) {
  const [workout, setWorkout] = useState(initial)
  const input = toUpdateInput(workout)

  function updateSet(exerciseIndex: number, setIndex: number, change: Partial<EditableSet>) {
    setWorkout((current) => ({
      ...current,
      exercises: current.exercises.map((exercise, i) =>
        i === exerciseIndex ? { ...exercise, sets: exercise.sets.map((set, j) => (j === setIndex ? { ...set, ...change } : set)) } : exercise,
      ),
    }))
  }

  function removeSet(exerciseIndex: number, setIndex: number) {
    setWorkout((current) => ({
      ...current,
      exercises: current.exercises.map((exercise, i) => (i === exerciseIndex ? { ...exercise, sets: exercise.sets.filter((_, j) => j !== setIndex) } : exercise)),
    }))
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (input) onSave(input)
      }}
    >
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="edit-workout-name">Workout name</Label>
        <Input
          id="edit-workout-name"
          value={workout.name}
          maxLength={60}
          disabled={saving}
          aria-invalid={!isWorkoutNameValid(workout.name) || undefined}
          onChange={(event) => setWorkout((current) => ({ ...current, name: event.target.value }))}
          className="h-10"
        />
      </div>

      {workout.exercises.map((exercise, exerciseIndex) => {
        const labels = historySetLabels(exercise.sets)
        return (
          <section key={`${exerciseIndex}-${exercise.exerciseId}`} className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">{exercise.name}</h3>
            {exercise.sets.length === 0 ? <p className="text-sm text-muted-foreground">All sets removed; this exercise won’t be saved.</p> : null}
            <ul className="flex flex-col gap-2">
              {exercise.sets.map((set, setIndex) => {
                const name = `${exercise.name} ${labels[setIndex]}`
                const invalid = !isEditableSetValid(set)
                return (
                  <li key={setIndex} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_3.5rem_2.5rem] items-center gap-1.5 sm:grid-cols-[7rem_minmax(0,1fr)_minmax(0,1fr)_4rem_2.5rem]">
                    <select
                      aria-label={`${name} type`}
                      value={set.kind}
                      disabled={saving}
                      onChange={(event) => updateSet(exerciseIndex, setIndex, { kind: event.target.value as SetKind })}
                      className="col-span-5 h-10 rounded-md border bg-background px-2 text-sm sm:col-span-1"
                    >
                      {SET_KINDS.map((kind) => (
                        <option key={kind} value={kind}>
                          {SET_KIND_LABELS[kind]}
                        </option>
                      ))}
                    </select>
                    <Input
                      aria-label={`${name} weight in kg`}
                      inputMode="decimal"
                      value={set.weight}
                      disabled={saving}
                      aria-invalid={invalid || undefined}
                      onChange={(event) => updateSet(exerciseIndex, setIndex, { weight: event.target.value })}
                      className="h-10 text-center"
                    />
                    <Input
                      aria-label={`${name} reps`}
                      inputMode="numeric"
                      value={set.reps}
                      disabled={saving}
                      aria-invalid={invalid || undefined}
                      onChange={(event) => updateSet(exerciseIndex, setIndex, { reps: event.target.value })}
                      className="h-10 text-center"
                    />
                    <Input
                      aria-label={`${name} RPE, optional`}
                      inputMode="decimal"
                      placeholder="RPE"
                      value={set.rpe}
                      disabled={saving}
                      aria-invalid={invalid || undefined}
                      onChange={(event) => updateSet(exerciseIndex, setIndex, { rpe: event.target.value })}
                      className="h-10 text-center"
                    />
                    <Button type="button" variant="ghost" size="icon" className="size-10 text-muted-foreground" aria-label={`Remove ${name}`} disabled={saving} onClick={() => removeSet(exerciseIndex, setIndex)}>
                      <Trash2 />
                    </Button>
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}

      {input === null ? (
        <p role="status" className="text-sm text-muted-foreground">
          Fix the highlighted values (weight 0–1000 kg, whole reps 0–100, RPE 1–10) and keep at least one set. To remove the whole workout, delete it instead.
        </p>
      ) : null}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" className="h-10" disabled={input === null || saving}>
          {saving ? <Spinner data-icon="inline-start" /> : null}
          Save changes
        </Button>
      </div>
    </form>
  )
}
