import { Dumbbell, Plus, Trash2 } from "lucide-react"
import { useMemo, useReducer, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { PageHeader } from "@/components/layout/page-header"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { ExerciseCard } from "@/components/workout/exercise-card"
import { ExercisePicker } from "@/components/workout/exercise-picker"
import { RestTimer } from "@/components/workout/rest-timer"
import { SessionOverview, StrengthHighlightCard } from "@/components/workout/session-overview"
import { SessionStatsLine } from "@/components/workout/session-stats"
import { StartWorkout } from "@/components/workout/start-workout"
import { WorkoutSummary } from "@/components/workout/workout-summary"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Progress } from "@/components/ui/progress"
import { Spinner } from "@/components/ui/spinner"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { useFinishWorkout, useTodayWorkout } from "@/hooks/use-workout"
import { initSession, sessionReducer, sessionTotals, toFinishInput, type SessionExercise } from "@/lib/workout-session"
import type { Exercise, PlannedWorkout, WorkoutSummary as WorkoutSummaryData } from "@/types/workout"

type Started = { kind: "plan" | "empty"; id: number }

export default function WorkoutPage() {
  const workout = useTodayWorkout()
  const [searchParams, setSearchParams] = useSearchParams()
  const [started, setStarted] = useState<Started | null>(null)

  // Home's "Start workout" links to ?start=plan and skips the chooser once the plan has loaded.
  const autoStartPlan = started === null && searchParams.get("start") === "plan" && Boolean(workout.data)
  const active: Started | null = started ?? (autoStartPlan ? { kind: "plan", id: 0 } : null)

  function start(kind: Started["kind"]) {
    setStarted((prev) => ({ kind, id: (prev?.id ?? 0) + 1 }))
  }

  function exit() {
    setStarted(null)
    if (searchParams.has("start")) setSearchParams({}, { replace: true })
  }

  if (active && (active.kind === "empty" || workout.data)) {
    const plan = active.kind === "plan" ? (workout.data ?? null) : null
    return <WorkoutSession key={`${active.kind}-${active.id}`} plan={plan} onExit={exit} />
  }

  return (
    <>
      <PageHeader eyebrow="Workout" title="Start a workout" />
      <StartWorkout
        plan={workout.data}
        planPending={workout.isPending}
        planError={workout.isError ? workout.error : null}
        onRetryPlan={() => void workout.refetch()}
        onStartPlan={() => start("plan")}
        onStartEmpty={() => start("empty")}
      />
    </>
  )
}

type Confirm = { kind: "finish" | "discard"; layout: OverlayLayout } | null

type WorkoutSessionProps = {
  /** Null for an empty workout. */
  plan: PlannedWorkout | null
  onExit: () => void
}

function WorkoutSession({ plan, onExit }: WorkoutSessionProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const [state, dispatch] = useReducer(sessionReducer, plan, initSession)
  const [startedAt] = useState(() => Date.now())
  const [pickerLayout, setPickerLayout] = useState<OverlayLayout | null>(null)
  const [pickerKey, setPickerKey] = useState(0)
  const [confirm, setConfirm] = useState<Confirm>(null)
  const [summary, setSummary] = useState<WorkoutSummaryData | null>(null)
  const finish = useFinishWorkout()

  const totals = useMemo(() => sessionTotals(state.exercises), [state.exercises])
  const remainingSets = totals.total - totals.done
  const percentDone = totals.total > 0 ? (totals.done / totals.total) * 100 : 0

  function openConfirm(kind: "finish" | "discard") {
    setConfirm({ kind, layout: isDesktop ? "dialog" : "drawer" })
  }

  function requestFinish() {
    if (totals.done === 0) {
      toast("Complete at least one set first", { description: "Tick a set once you’ve done it." })
      return
    }
    if (remainingSets > 0) openConfirm("finish")
    else submitFinish()
  }

  function submitFinish() {
    finish.mutate(toFinishInput(state, startedAt, Date.now()), {
      onSuccess: (result) => {
        setConfirm(null)
        setSummary(result)
      },
      onError: (error) => toast.error("Couldn’t save your workout", { description: `${apiErrorMessage(error)} Your sets are still here.` }),
    })
  }

  function discard() {
    setConfirm(null)
    toast("Workout discarded")
    onExit()
  }

  function openPicker() {
    setPickerKey((key) => key + 1)
    setPickerLayout(isDesktop ? "dialog" : "drawer")
  }

  function addExercises(exercises: Exercise[]) {
    setPickerLayout(null)
    dispatch({ type: "add-exercises", exercises })
    toast.success(exercises.length === 1 ? `Added ${exercises[0].name}` : `Added ${exercises.length} exercises`)
  }

  function removeExercise(exercise: SessionExercise) {
    const index = state.exercises.findIndex((e) => e.id === exercise.id)
    dispatch({ type: "remove-exercise", exerciseId: exercise.id })
    toast(`Removed ${exercise.name}`, {
      action: { label: "Undo", onClick: () => dispatch({ type: "restore-exercise", exercise, index }) },
    })
  }

  if (summary) {
    return (
      <>
        <PageHeader eyebrow={plan?.weekLabel ?? "Workout"} title="Nice work" />
        <WorkoutSummary summary={summary} />
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow={plan ? `Workout in progress · ${plan.weekLabel}` : "Workout in progress"}
        title={state.name}
        actions={
          <>
            <Button variant="outline" className="hidden h-10 lg:inline-flex" onClick={openPicker}>
              <Plus data-icon="inline-start" />
              Add exercise
            </Button>
            <Button variant="ghost" className="hidden h-10 lg:inline-flex" onClick={() => openConfirm("discard")}>
              Discard
            </Button>
            <Button className="h-10" onClick={requestFinish} disabled={finish.isPending || totals.total === 0}>
              {finish.isPending ? <Spinner data-icon="inline-start" /> : null}
              {isDesktop ? "Finish workout" : "Finish"}
            </Button>
          </>
        }
      />

      <div className="flex flex-col gap-2 lg:hidden">
        <SessionStatsLine startedAt={startedAt} {...totals} />
        <Progress value={percentDone} aria-label="Sets completed" />
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-6">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-8">
          <RestTimer rest={state.rest} dispatch={dispatch} className="sticky top-3 z-10 lg:hidden" />
          {state.exercises.length === 0 ? (
            <Empty className="border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Dumbbell />
                </EmptyMedia>
                <EmptyTitle>Add your first exercise</EmptyTitle>
                <EmptyDescription>Search the library or create your own. Sets fill in from your last session.</EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button className="h-11" onClick={openPicker}>
                  <Plus data-icon="inline-start" />
                  Add exercises
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            state.exercises.map((exercise, index) => (
              <ExerciseCard
                key={exercise.id}
                exercise={exercise}
                isFirst={index === 0}
                isLast={index === state.exercises.length - 1}
                dispatch={dispatch}
                onRemove={removeExercise}
              />
            ))
          )}
          <div className="flex flex-col gap-2 lg:hidden">
            <Button variant="outline" className="h-12 w-full" onClick={openPicker} hidden={state.exercises.length === 0}>
              <Plus data-icon="inline-start" />
              Add exercise
            </Button>
            <Button variant="ghost" className="h-11 w-full text-destructive" onClick={() => openConfirm("discard")}>
              <Trash2 data-icon="inline-start" />
              Discard workout
            </Button>
          </div>
        </div>

        {isDesktop ? (
          <aside className="sticky top-7 flex flex-col gap-4 lg:col-span-4">
            <RestTimer rest={state.rest} dispatch={dispatch} />
            <SessionOverview startedAt={startedAt} exercises={state.exercises} totals={totals} />
            {plan?.highlight ? <StrengthHighlightCard highlight={plan.highlight} /> : null}
          </aside>
        ) : null}
      </div>

      <ResponsiveOverlay
        open={confirm?.kind === "finish"}
        onOpenChange={(open) => (open ? undefined : setConfirm(null))}
        layout={confirm?.layout ?? "dialog"}
        title="Finish with sets left?"
        description={`${remainingSets} planned set${remainingSets === 1 ? " isn’t" : "s aren’t"} ticked. Only completed sets will be saved.`}
      >
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" className="h-10" onClick={() => setConfirm(null)} disabled={finish.isPending}>
            Keep going
          </Button>
          <Button className="h-10" onClick={submitFinish} disabled={finish.isPending}>
            {finish.isPending ? <Spinner data-icon="inline-start" /> : null}
            Finish anyway
          </Button>
        </div>
      </ResponsiveOverlay>

      <ResponsiveOverlay
        open={confirm?.kind === "discard"}
        onOpenChange={(open) => (open ? undefined : setConfirm(null))}
        layout={confirm?.layout ?? "dialog"}
        title="Discard this workout?"
        description="Nothing from this session will be saved. This can’t be undone."
      >
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="outline" className="h-10" onClick={() => setConfirm(null)}>
            Cancel
          </Button>
          <Button variant="destructive" className="h-10" onClick={discard}>
            Discard
          </Button>
        </div>
      </ResponsiveOverlay>

      <ResponsiveOverlay
        open={pickerLayout !== null}
        onOpenChange={(open) => (open ? undefined : setPickerLayout(null))}
        layout={pickerLayout ?? "dialog"}
        title="Add exercises"
        description="Search the library, pick one or more, or create your own."
        hideDescription
        className="sm:max-w-lg"
      >
        <ExercisePicker key={pickerKey} onAdd={addExercises} />
      </ResponsiveOverlay>
    </>
  )
}
