import { ArrowDown, ArrowUp, Dumbbell, Minus, Plus, Trash2 } from "lucide-react"
import { useReducer, useState, type Dispatch } from "react"

import { ConfirmOverlay } from "@/components/layout/confirm-overlay"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { ExercisePicker } from "@/components/workout/exercise-picker"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { TextField } from "@/components/ui/text-field"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useOverlayLayout } from "@/hooks/use-media-query"
import {
  ROUTINE_LIMITS,
  canSaveDraft,
  draftFromRoutine,
  rangeError,
  routineDraftReducer,
  toSaveRoutineInput,
  type DraftAction,
  type DraftExercise,
} from "@/lib/routine-draft"
import { WEEKDAY_LABELS, type PlannedWorkout, type SaveRoutineInput, type SetKind } from "@/types/workout"

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
  const overlayLayout = useOverlayLayout()
  const [draft, dispatch] = useReducer(routineDraftReducer, routine, draftFromRoutine)
  const [confirmDelete, setConfirmDelete] = useState<OverlayLayout | null>(null)
  const [picker, setPicker] = useState<OverlayLayout | null>(null)
  const { exercises } = draft
  const nameMissing = draft.name.trim() === ""

  return (
    <div className="flex flex-col gap-4">
      <FieldGroup className="sm:max-w-sm">
        <TextField
          id="routine-name"
          label="Name"
          value={draft.name}
          maxLength={60}
          error={nameMissing ? "Give the routine a name" : undefined}
          onChange={(event) => dispatch({ type: "rename", name: event.target.value })}
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
            <Button onClick={() => setPicker(overlayLayout)}>
              <Plus data-icon="inline-start" />
              Add exercises
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {exercises.map((exercise, index) => (
            <RoutineExerciseCard
              key={exercise.instanceId}
              exercise={exercise}
              isFirst={index === 0}
              isLast={index === exercises.length - 1}
              dispatch={dispatch}
            />
          ))}

          <Button variant="outline" className="h-11 w-full border-dashed" onClick={() => setPicker(overlayLayout)}>
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
            <Button variant="outline" className="h-10 text-destructive" onClick={() => setConfirmDelete(overlayLayout)} disabled={submitting || deleting}>
              Delete routine
            </Button>
          ) : null}
        </div>
        <Button className="h-10" onClick={() => onSave(toSaveRoutineInput(draft))} disabled={!canSaveDraft(draft) || submitting}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Save routine
        </Button>
      </div>

      <ConfirmOverlay
        layout={confirmDelete}
        onClose={() => setConfirmDelete(null)}
        title="Delete this routine?"
        description={
          scheduledDays.length > 0
            ? `It will also be removed from ${scheduledDays.map((day) => WEEKDAY_LABELS[day]).join(", ")}, which become rest days. Workouts you already logged are kept.`
            : "Workouts you already logged from it are kept."
        }
        confirmLabel="Delete routine"
        destructive
        pending={deleting}
        onConfirm={onDelete}
      />

      <ResponsiveOverlay
        open={picker !== null}
        onOpenChange={(open) => (open ? undefined : setPicker(null))}
        layout={picker ?? "dialog"}
        title="Add exercises"
        description="Search the library, pick one or more, or create your own."
        hideDescription
        dialogClassName="sm:max-w-lg"
      >
        <ExercisePicker
          onAdd={(picked) => {
            setPicker(null)
            dispatch({ type: "add-exercises", exercises: picked })
          }}
        />
      </ResponsiveOverlay>
    </div>
  )
}

type RoutineExerciseCardProps = {
  exercise: DraftExercise
  isFirst: boolean
  isLast: boolean
  dispatch: Dispatch<DraftAction>
}

function RoutineExerciseCard({ exercise, isFirst, isLast, dispatch }: RoutineExerciseCardProps) {
  const { instanceId } = exercise
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{exercise.name}</CardTitle>
        <div className="ml-auto flex items-center">
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-9 text-muted-foreground"
            aria-label={`Move ${exercise.name} up`}
            disabled={isFirst}
            onClick={() => dispatch({ type: "move", instanceId, direction: -1 })}
          >
            <ArrowUp className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-9 text-muted-foreground"
            aria-label={`Move ${exercise.name} down`}
            disabled={isLast}
            onClick={() => dispatch({ type: "move", instanceId, direction: 1 })}
          >
            <ArrowDown className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-9 text-muted-foreground"
            aria-label={`Remove ${exercise.name}`}
            onClick={() => dispatch({ type: "remove", instanceId })}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <TextField
          id={`${instanceId}-rest`}
          label="Rest between sets"
          className="max-w-40"
          unit="sec"
          inputMode="numeric"
          value={exercise.restSeconds}
          error={rangeError(exercise.restSeconds, ROUTINE_LIMITS.rest)}
          onChange={(event) => dispatch({ type: "set-rest", instanceId, value: event.target.value })}
        />

        <ul className="flex flex-col gap-2">
          {exercise.sets.map((set, index) => (
            <li key={set.id} className="grid grid-cols-[5.5rem_1fr_1fr_2.5rem] items-center gap-2">
              <ToggleGroup
                type="single"
                variant="outline"
                spacing={0}
                value={set.kind}
                onValueChange={(next) => (next ? dispatch({ type: "edit-set", instanceId, setId: set.id, patch: { kind: next as SetKind } }) : undefined)}
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
                error={rangeError(set.targetWeightKg, ROUTINE_LIMITS.weight)}
                onChange={(event) => dispatch({ type: "edit-set", instanceId, setId: set.id, patch: { targetWeightKg: event.target.value } })}
              />
              <TextField
                id={`${set.id}-reps`}
                label=""
                unit="reps"
                inputMode="numeric"
                placeholder="Target"
                value={set.targetReps}
                error={rangeError(set.targetReps, ROUTINE_LIMITS.reps)}
                onChange={(event) => dispatch({ type: "edit-set", instanceId, setId: set.id, patch: { targetReps: event.target.value } })}
              />
              <Button
                variant="ghost"
                size="icon-lg"
                className="size-9"
                aria-label={`Remove set ${index + 1}`}
                disabled={exercise.sets.length <= 1}
                onClick={() => dispatch({ type: "remove-set", instanceId, setId: set.id })}
              >
                <Minus className="size-4" />
              </Button>
            </li>
          ))}
        </ul>

        <Button variant="outline" className="h-10 w-full" onClick={() => dispatch({ type: "add-set", instanceId })}>
          <Plus data-icon="inline-start" />
          Add set
        </Button>
      </CardContent>
    </Card>
  )
}
