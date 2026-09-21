import { Dumbbell, Minus, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { createRequestId } from "@/api/client"
import { TextField } from "@/components/food/form-field"
import { ResponsiveOverlay } from "@/components/layout/responsive-overlay"
import { ExercisePicker } from "@/components/workout/exercise-picker"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { toNumber } from "@/lib/format"
import type { Exercise, PlannedWorkout, SavePlanDayInput, SetKind } from "@/types/workout"

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

function fromPlan(plan: PlannedWorkout | null, dayLabel: string) {
  if (!plan) return { name: `${dayLabel} workout`, weekLabel: "Week 1", estimatedMinutes: "45", exercises: [] as EditorExercise[] }
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

type PlanDayEditorProps = {
  dayLabel: string
  plan: PlannedWorkout | null
  submitting: boolean
  deleting: boolean
  onSave: (input: SavePlanDayInput) => void
  onClearDay: () => void
  onCancel: () => void
}

export function PlanDayEditor({ dayLabel, plan, submitting, deleting, onSave, onClearDay, onCancel }: PlanDayEditorProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const [initial] = useState(() => fromPlan(plan, dayLabel))
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
    const input: SavePlanDayInput = {
      name: name.trim() || `${dayLabel} workout`,
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

  const canSave = exercises.length > 0 && exercises.every((exercise) => exercise.sets.length > 0) && !submitting

  return (
    <div className="flex flex-col gap-4">
      <FieldGroup className="grid gap-4 sm:grid-cols-3">
        <TextField id="plan-day-name" label="Name" value={name} onChange={(event) => setName(event.target.value)} />
        <TextField id="plan-day-week-label" label="Week label" value={weekLabel} onChange={(event) => setWeekLabel(event.target.value)} />
        <TextField
          id="plan-day-minutes"
          label="Estimated time"
          unit="min"
          inputMode="numeric"
          value={estimatedMinutes}
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
            <EmptyDescription>Add exercises to plan this day, or leave it empty and clear it to a rest day.</EmptyDescription>
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
          {exercises.map((exercise) => (
            <Card key={exercise.instanceId}>
              <CardHeader>
                <CardTitle className="text-base">{exercise.name}</CardTitle>
                <Button
                  variant="ghost"
                  size="icon-lg"
                  className="ml-auto size-9 text-muted-foreground"
                  aria-label={`Remove ${exercise.name}`}
                  onClick={() => removeExercise(exercise.instanceId)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <TextField
                  id={`${exercise.instanceId}-rest`}
                  label="Rest between sets"
                  className="max-w-40"
                  unit="sec"
                  inputMode="numeric"
                  value={exercise.restSeconds}
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
                        onChange={(event) => updateSet(exercise.instanceId, set.id, { targetWeightKg: event.target.value })}
                      />
                      <TextField
                        id={`${set.id}-reps`}
                        label=""
                        unit="reps"
                        inputMode="numeric"
                        placeholder="Target"
                        value={set.targetReps}
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
          {plan ? (
            <Button variant="outline" className="h-10 text-destructive" onClick={onClearDay} disabled={submitting || deleting}>
              {deleting ? <Spinner data-icon="inline-start" /> : null}
              Clear to rest day
            </Button>
          ) : null}
        </div>
        <Button className="h-10" onClick={submit} disabled={!canSave}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Save day
        </Button>
      </div>

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
