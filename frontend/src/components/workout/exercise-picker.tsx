import { format, parseISO } from "date-fns"
import { Check, Plus, RotateCw, Search, SearchX } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { CreateExerciseForm } from "@/components/workout/create-exercise-form"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { useCreateExercise, useExerciseSearch } from "@/hooks/use-workout"
import { formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"
import { EQUIPMENT, EQUIPMENT_LABELS, MUSCLE_GROUPS, MUSCLE_LABELS, type Equipment, type Exercise, type MuscleGroup } from "@/types/workout"

const ALL = "all"

type ExercisePickerProps = {
  onAdd: (exercises: Exercise[]) => void
}

function lastSessionLabel(exercise: Exercise) {
  const session = exercise.lastSession
  if (!session?.sets.length) return null
  const top = session.sets.reduce((best, set) => (set.weightKg * set.reps > best.weightKg * best.reps ? set : best))
  const load = top.weightKg > 0 ? `${formatNumber(top.weightKg, 1)} kg × ${top.reps}` : `${top.reps} reps`
  return `Last: ${load} · ${format(parseISO(session.date), "d MMM")}`
}

/** Search the exercise library, multi-select, or create a custom exercise. Mounted fresh each time the overlay opens. */
export function ExercisePicker({ onAdd }: ExercisePickerProps) {
  const [query, setQuery] = useState("")
  const [muscle, setMuscle] = useState<MuscleGroup | typeof ALL>(ALL)
  const [equipment, setEquipment] = useState<Equipment | typeof ALL>(ALL)
  // Map keeps the order of selection and the full exercise, even if it scrolls out of the filtered results.
  const [selected, setSelected] = useState<Map<string, Exercise>>(() => new Map())
  const [creating, setCreating] = useState(false)

  const debouncedQuery = useDebouncedValue(query.trim(), 250)
  const filters = { q: debouncedQuery, muscle: muscle === ALL ? undefined : muscle, equipment: equipment === ALL ? undefined : equipment }
  const search = useExerciseSearch(filters)
  const createExercise = useCreateExercise()

  const results = search.data ?? []
  const settling = query.trim() !== debouncedQuery || search.isFetching
  const filtered = muscle !== ALL || equipment !== ALL

  function toggle(exercise: Exercise) {
    setSelected((prev) => {
      const next = new Map(prev)
      if (next.has(exercise.id)) next.delete(exercise.id)
      else next.set(exercise.id, exercise)
      return next
    })
  }

  if (creating) {
    return (
      <CreateExerciseForm
        defaultName={query.trim()}
        submitting={createExercise.isPending}
        onBack={() => setCreating(false)}
        onSubmit={(input) =>
          createExercise.mutate(input, {
            onSuccess: (created) => {
              toast.success(`Created ${created.name}`, { description: "Saved to your exercises and added to this workout." })
              onAdd([...selected.values(), created])
            },
            onError: (error) => toast.error("Couldn’t create that exercise", { description: apiErrorMessage(error) }),
          })
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <InputGroup className="h-11">
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          type="search"
          autoFocus
          autoComplete="off"
          aria-label="Search exercises"
          placeholder="Search exercises"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {settling ? (
          <InputGroupAddon align="inline-end">
            <Spinner />
          </InputGroupAddon>
        ) : null}
      </InputGroup>

      <div className="grid grid-cols-2 gap-2">
        <Select value={muscle} onValueChange={(value) => setMuscle(value as MuscleGroup | typeof ALL)}>
          <SelectTrigger className="w-full data-[size=default]:h-10" aria-label="Filter by muscle">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All muscles</SelectItem>
            {MUSCLE_GROUPS.map((group) => (
              <SelectItem key={group} value={group}>
                {MUSCLE_LABELS[group]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={equipment} onValueChange={(value) => setEquipment(value as Equipment | typeof ALL)}>
          <SelectTrigger className="w-full data-[size=default]:h-10" aria-label="Filter by equipment">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All equipment</SelectItem>
            {EQUIPMENT.map((item) => (
              <SelectItem key={item} value={item}>
                {EQUIPMENT_LABELS[item]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {search.isError ? (
        <Alert variant="destructive">
          <AlertTitle>Couldn’t load exercises</AlertTitle>
          <AlertDescription>{apiErrorMessage(search.error)}</AlertDescription>
          <AlertAction>
            <Button variant="outline" size="sm" onClick={() => void search.refetch()}>
              <RotateCw data-icon="inline-start" />
              Retry
            </Button>
          </AlertAction>
        </Alert>
      ) : search.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading exercises">
          {[0, 1, 2, 3, 4].map((key) => (
            <Skeleton key={key} className="h-14 w-full" />
          ))}
        </div>
      ) : results.length === 0 ? (
        <Empty className="border py-8">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchX />
            </EmptyMedia>
            <EmptyTitle>{debouncedQuery ? `No exercises match “${debouncedQuery}”` : "No exercises match these filters"}</EmptyTitle>
            <EmptyDescription>{filtered ? "Try clearing the filters, or create it as your own exercise." : "Create it as your own exercise."}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent className="flex-row flex-wrap justify-center">
            {filtered ? (
              <Button
                variant="outline"
                onClick={() => {
                  setMuscle(ALL)
                  setEquipment(ALL)
                }}
              >
                Clear filters
              </Button>
            ) : null}
            <Button onClick={() => setCreating(true)}>
              <Plus data-icon="inline-start" />
              Create exercise
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <ul className={cn("-mx-1 flex max-h-[45dvh] flex-col gap-1 overflow-y-auto px-1 lg:max-h-96", search.isPlaceholderData && "opacity-60")} aria-label="Exercises">
          {results.map((exercise) => {
            const isSelected = selected.has(exercise.id)
            const last = lastSessionLabel(exercise)
            return (
              <li key={exercise.id}>
                <button
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => toggle(exercise)}
                  className={cn(
                    "flex min-h-14 w-full items-center gap-3 rounded-lg border border-transparent px-3 py-2 text-left transition-colors outline-none hover:bg-muted/60 focus-visible:ring-3 focus-visible:ring-ring/50",
                    isSelected && "border-primary/45 bg-primary/7",
                  )}
                >
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{exercise.name}</span>
                      {exercise.source === "custom" ? <Badge variant="outline">Custom</Badge> : null}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {EQUIPMENT_LABELS[exercise.equipment]} · {exercise.muscles.map((m) => MUSCLE_LABELS[m]).join(", ")}
                      {last ? ` · ${last}` : ""}
                    </span>
                  </span>
                  <span
                    aria-hidden
                    className={cn(
                      "flex size-6 shrink-0 items-center justify-center rounded-md border",
                      isSelected ? "border-primary bg-primary text-primary-foreground" : "border-input text-transparent",
                    )}
                  >
                    <Check className="size-4" />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      <div className="flex flex-col-reverse gap-2 border-t pt-3 sm:flex-row sm:items-center sm:justify-between">
        <Button variant="ghost" className="h-10 min-w-0" onClick={() => setCreating(true)}>
          <Plus data-icon="inline-start" />
          <span className="truncate">{query.trim() ? `Create “${query.trim()}”` : "Create exercise"}</span>
        </Button>
        <Button className="h-11 sm:min-w-40" disabled={selected.size === 0} onClick={() => onAdd([...selected.values()])}>
          {selected.size === 0 ? "Select exercises" : `Add ${selected.size} exercise${selected.size === 1 ? "" : "s"}`}
        </Button>
      </div>
    </div>
  )
}
