import { ArrowDown, ArrowUp, Dumbbell, Minus, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { createRequestId } from "@/api/client"
import { TextField } from "@/components/ui/text-field"
import { ResponsiveOverlay } from "@/components/layout/responsive-overlay"
import { ExercisePicker } from "@/components/workout/exercise-picker"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { formatNumber, toNumber } from "@/lib/format"
import { WEEKDAY_LABELS, type Exercise, type PlannedWorkout, type SaveRoutineInput, type SetKind } from "@/types/workout"

/** What the server accepts for a routine; blank fields take a default (time, rest) or mean no target. */
const LIMITS = {
  minutes: { min: 1, max: 600, whole: true },
  rest: { min: 0, max: 600, whole: true },
  weight: { min: 0, max: 1_000, whole: false },
  reps: { min: 1, max: 100, whole: true },
} as const

function rangeError(raw: string, { min, max, whole }: { min: number; max: number; whole: boolean }) {
  if (raw.trim() === "") return undefined
  const value = toNumber(raw)
  if (value === undefined) return "Enter a number"
  if (whole && !Number.isInteger(value)) return "Whole number"
  if (value < min || value > max) return `${formatNumber(min)}–${formatNumber(max)}`
  return undefined
}

type EditorSet = { id: string; kind: SetKind; targetWeightKg: string; targetReps: string }

type EditorExercise = {
  instanceId: string
  exerciseId: string
  name: string
  equipment: string
  muscles: string
  restSeconds: string
  sets: EditorSet[]
}

function fromRoutine(plan: PlannedWorkout | null) {
  if (!plan) return { name: "New routine", weekLabel: "Week 1", estimatedMinutes: "45", exercises: [] as EditorExercise[] }
  return {
    name: plan.name,
    weekLabel: plan.weekLabel,
    estimatedMinutes: String(plan.estimatedMinutes),
    exercises: plan.exercises.map((exercise, index) => ({
      instanceId: `${exercise.id}-${index}`,
      exerciseId: exercise.id,
      name: exercise.name,
      equipment: exercise.equipment,
      muscles: exercise.muscles,
      restSeconds: String(exercise.restSeconds),
      sets: exercise.sets.map((set) => ({
        id: set.id,
        kind: set.kind,
        targetWeightKg: set.targetWeightKg == null ? "" : String(set.targetWeightKg),
        targetReps: set.targetReps == null ? "" : String(set.targetReps),
      })),
    })),
  }
}

function newSet(kind: SetKind, id: string): EditorSet {
  return { id, kind, targetWeightKg: "", targetReps: "" }
}

type RoutineEditorProps = {
  /** The routine being edited, or null to create a new one. */
  routine: PlannedWorkout | null
  /** Weekdays (0=Monday) the routine is scheduled on, named in the delete confirmation. */
  scheduledDays?: number[]
  submitting: boolean
  deleting: boolean
  onSave: (input: SaveRoutineInput) => void
  onDelete: () => void
  onCancel: () => void
}

export function RoutineEditor({ routine, scheduledDays = [], submitting, deleting, onSave, onDelete, onCancel }: RoutineEditorProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [initial] = useState(() => fromRoutine(routine))
  const [name, setName] = useState(initial.name)
  const [weekLabel, setWeekLabel] = useState(initial.weekLabel)
  const [estimatedMinutes, setEstimatedMinutes] = useState(initial.estimatedMinutes)
  const [exercises, setExercises] = useState<EditorExercise[]>(initial.exercises)
  const [pickerOpen, setPickerOpen] = useState(false)

  function addExercises(picked: Exercise[]) {
    setPickerOpen(false)
    const added = picked.map((exercise) => {
      const id = createRequestId()
      return {
        instanceId: `${exercise.id}-new-${id}`,
        exerciseId: exercise.id,
        name: exercise.name,
        equipment: exercise.equipment,
        muscles: exercise.muscles.join(", "),
        restSeconds: "90",
        sets: [newSet("warmup", `${exercise.id}-new-${id}-w1`), newSet("working", `${exercise.id}-new-${id}-s1`), newSet("working", `${exercise.id}-new-${id}-s2`)],
      }
    })
    setExercises((prev) => [...prev, ...added])
  }

  function moveExercise(instanceId: string, direction: -1 | 1) {
    setExercises((prev) => {
      const from = prev.findIndex((exercise) => exercise.instanceId === instanceId)
      const to = from + direction
      if (from < 0 || to < 0 || to >= prev.length) return prev
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(to, 0, moved)
      return next
    })
  }

  function removeExercise(instanceId: string) {
    setExercises((prev) => prev.filter((exercise) => exercise.instanceId !== instanceId))
  }

  function updateExercise(instanceId: string, patch: Partial<EditorExercise>) {
    setExercises((prev) => prev.map((exercise) => (exercise.instanceId === instanceId ? { ...exercise, ...patch } : exercise)))
  }

  function addSet(instanceId: string) {
    const id = createRequestId()
    updateExerciseSets(instanceId, (sets) => [...sets, newSet("working", `${instanceId}-extra-${id}`)])
  }

  function removeSet(instanceId: string, setId: string) {
    updateExerciseSets(instanceId, (sets) => (sets.length > 1 ? sets.filter((set) => set.id !== setId) : sets))
  }

  function updateSet(instanceId: string, setId: string, patch: Partial<EditorSet>) {
    updateExerciseSets(instanceId, (sets) => sets.map((set) => (set.id === setId ? { ...set, ...patch } : set)))
  }

  function updateExerciseSets(instanceId: string, update: (sets: EditorSet[]) => EditorSet[]) {
    setExercises((prev) => prev.map((exercise) => (exercise.instanceId === instanceId ? { ...exercise, sets: update(exercise.sets) } : exercise)))
  }

  function submit() {
    const input: SaveRoutineInput = {
      name: name.trim(),
      weekLabel: weekLabel.trim() || "Week 1",
      estimatedMinutes: toNumber(estimatedMinutes) ?? 45,
      exercises: exercises.map((exercise) => ({
        exerciseId: exercise.exerciseId,
        restSeconds: toNumber(exercise.restSeconds) ?? 90,
        sets: exercise.sets.map((set) => ({
          kind: set.kind,
          targetWeightKg: toNumber(set.targetWeightKg) ?? null,
          targetReps: toNumber(set.targetReps) ?? null,
        })),
      })),
    }
    onSave(input)
  }

  // A name is required: it is how the routine is picked in the week schedule.
  const nameMissing = name.trim() === ""
  const minutesError = rangeError(estimatedMinutes, LIMITS.minutes)
  const outOfRange =
    minutesError !== undefined ||
    exercises.some(
      (exercise) =>
        rangeError(exercise.restSeconds, LIMITS.rest) !== undefined ||
        exercise.sets.some((set) => rangeError(set.targetWeightKg, LIMITS.weight) !== undefined || rangeError(set.targetReps, LIMITS.reps) !== undefined),
    )
  const canSave = !nameMissing && !outOfRange && exercises.length > 0 && exercises.every((exercise) => exercise.sets.length > 0) && !submitting

  return (
    <div className="flex flex-col gap-4">
      <FieldGroup className="grid gap-4 sm:grid-cols-3">
        <TextField id="routine-name" label="Name" value={name} maxLength={60} error={nameMissing ? "Give the routine a name" : undefined} onChange={(event) => setName(event.target.value)} />
        <TextField id="routine-week-label" label="Week label" value={weekLabel} maxLength={64} onChange={(event) => setWeekLabel(event.target.value)} />
        <TextField
          id="routine-minutes"
          label="Estimated time"
          unit="min"
          inputMode="numeric"
          value={estimatedMinutes}
          error={minutesError}
          onChange={(event) => setEstimatedMinutes(event.target.value)}
        />
      </FieldGroup>

      {exercises.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Dumbbell />
            </EmptyMedia>
            <EmptyTitle>No exercises yet</EmptyTitle>
            <EmptyDescription>Add the exercises this routine is made of.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button onClick={() => setPickerOpen(true)}>
              <Plus data-icon="inline-start" />
              Add exercises
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {exercises.map((exercise, index) => (
            <Card key={exercise.instanceId}>
              <CardHeader>
                <CardTitle className="text-base">{exercise.name}</CardTitle>
                <div className="ml-auto flex items-center">
                  <Button
                    variant="ghost"
                    size="icon-lg"
                    className="size-9 text-muted-foreground"
                    aria-label={`Move ${exercise.name} up`}
                    disabled={index === 0}
                    onClick={() => moveExercise(exercise.instanceId, -1)}
                  >
                    <ArrowUp className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-lg"
                    className="size-9 text-muted-foreground"
                    aria-label={`Move ${exercise.name} down`}
                    disabled={index === exercises.length - 1}
                    onClick={() => moveExercise(exercise.instanceId, 1)}
                  >
                    <ArrowDown className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-lg"
                    className="size-9 text-muted-foreground"
                    aria-label={`Remove ${exercise.name}`}
                    onClick={() => removeExercise(exercise.instanceId)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <TextField
                  id={`${exercise.instanceId}-rest`}
                  label="Rest between sets"
                  className="max-w-40"
                  unit="sec"
                  inputMode="numeric"
                  value={exercise.restSeconds}
                  error={rangeError(exercise.restSeconds, LIMITS.rest)}
                  onChange={(event) => updateExercise(exercise.instanceId, { restSeconds: event.target.value })}
                />

                <ul className="flex flex-col gap-2">
                  {exercise.sets.map((set, index) => (
                    <li key={set.id} className="grid grid-cols-[5.5rem_1fr_1fr_2.5rem] items-center gap-2">
                      <ToggleGroup
                        type="single"
                        variant="outline"
                        spacing={0}
                        value={set.kind}
                        onValueChange={(next) => (next ? updateSet(exercise.instanceId, set.id, { kind: next as SetKind }) : undefined)}
                        aria-label={`Set ${index + 1} kind`}
                      >
                        <ToggleGroupItem value="warmup" className="h-9 px-2 text-xs">
                          Warm
                        </ToggleGroupItem>
                        <ToggleGroupItem value="working" className="h-9 px-2 text-xs">
                          Work
                        </ToggleGroupItem>
                      </ToggleGroup>
                      <TextField
                        id={`${set.id}-weight`}
                        label=""
                        unit="kg"
                        inputMode="decimal"
                        placeholder="Target"
                        value={set.targetWeightKg}
                        error={rangeError(set.targetWeightKg, LIMITS.weight)}
                        onChange={(event) => updateSet(exercise.instanceId, set.id, { targetWeightKg: event.target.value })}
                      />
                      <TextField
                        id={`${set.id}-reps`}
                        label=""
                        unit="reps"
                        inputMode="numeric"
                        placeholder="Target"
                        value={set.targetReps}
                        error={rangeError(set.targetReps, LIMITS.reps)}
                        onChange={(event) => updateSet(exercise.instanceId, set.id, { targetReps: event.target.value })}
                      />
                      <Button
                        variant="ghost"
                        size="icon-lg"
                        className="size-9"
                        aria-label={`Remove set ${index + 1}`}
                        disabled={exercise.sets.length <= 1}
                        onClick={() => removeSet(exercise.instanceId, set.id)}
                      >
                        <Minus className="size-4" />
                      </Button>
                    </li>
                  ))}
                </ul>

                <Button variant="outline" className="h-10 w-full" onClick={() => addSet(exercise.instanceId)}>
                  <Plus data-icon="inline-start" />
                  Add set
                </Button>
              </CardContent>
            </Card>
          ))}

          <Button variant="outline" className="h-11 w-full border-dashed" onClick={() => setPickerOpen(true)}>
            <Plus data-icon="inline-start" />
            Add exercise
          </Button>
        </div>
      )}

      <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:justify-between">
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          <Button variant="ghost" className="h-10" onClick={onCancel} disabled={submitting || deleting}>
            Cancel
          </Button>
          {routine ? (
            <Button variant="outline" className="h-10 text-destructive" onClick={() => setConfirmDelete(true)} disabled={submitting || deleting}>
              Delete routine
            </Button>
          ) : null}
        </div>
        <Button className="h-10" onClick={submit} disabled={!canSave}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Save routine
        </Button>
      </div>

      <ResponsiveOverlay
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        layout={isDesktop ? "dialog" : "drawer"}
        title="Delete this routine?"
        description={
          scheduledDays.length > 0
            ? `It will also be removed from ${scheduledDays.map((day) => WEEKDAY_LABELS[day]).join(", ")}, which become rest days. Workouts you already logged are kept.`
            : "Workouts you already logged from it are kept."
        }
      >
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" className="h-10" onClick={() => setConfirmDelete(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="destructive" className="h-10" onClick={onDelete} disabled={deleting}>
            {deleting ? <Spinner data-icon="inline-start" /> : null}
            Delete routine
          </Button>
        </div>
      </ResponsiveOverlay>

      <ResponsiveOverlay
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        layout={isDesktop ? "dialog" : "drawer"}
        title="Add exercises"
        description="Search the library, pick one or more, or create your own."
        hideDescription
        className="sm:max-w-lg"
      >
        <ExercisePicker onAdd={addExercises} />
      </ResponsiveOverlay>
    </div>
  )
}
