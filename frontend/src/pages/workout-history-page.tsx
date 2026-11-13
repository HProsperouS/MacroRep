import { format, parseISO } from "date-fns"
import { History } from "lucide-react"
import { useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { HistoryRow } from "@/components/workout/history-row"
import { useWorkoutHistory } from "@/hooks/use-workout"
import { dayKey, HISTORY_PRESET_LABELS, HISTORY_PRESETS, isHistoryPreset, rangeError, rangeFor, type HistoryPreset } from "@/lib/history-range"
import type { HistoryRange } from "@/types/workout"

/** Shorter labels where five options have to share a phone's width. */
const SHORT_LABELS: Partial<Record<HistoryPreset, string>> = { week: "Week", month: "Month" }

function describeRange({ from, to }: HistoryRange) {
  const day = (value: string) => format(parseISO(value), "d MMM yyyy")
  if (from && to) return from === to ? day(from) : `${day(from)} – ${day(to)}`
  if (from) return `Since ${day(from)}`
  if (to) return `Up to ${day(to)}`
  return null
}

export default function WorkoutHistoryPage() {
  const navigate = useNavigate()
  const [today] = useState(() => new Date())
  // The filter lives in the URL so it survives reloads and Back, and Home can link to "Today".
  const [searchParams, setSearchParams] = useSearchParams()
  const rangeParam = searchParams.get("range")
  const preset: HistoryPreset = isHistoryPreset(rangeParam) ? rangeParam : "all"
  const custom = { from: searchParams.get("from") ?? undefined, to: searchParams.get("to") ?? undefined }
  const range = rangeFor(preset, today, custom)
  const error = rangeError(range)

  const history = useWorkoutHistory(range, error === null)
  const workouts = history.data?.pages.flat()
  const filtered = preset !== "all"

  function choosePreset(next: string) {
    if (!isHistoryPreset(next)) return // Radix emits "" when the active item is clicked again.
    if (next === "all") setSearchParams({}, { replace: true })
    else if (next === "custom") setSearchParams({ range: "custom", ...definedParams(custom.from || rangeFor("week", today).from, custom.to || dayKey(today)) }, { replace: true })
    else setSearchParams({ range: next }, { replace: true })
  }

  function setCustom(field: "from" | "to", value: string) {
    const next = { ...custom, [field]: value || undefined }
    setSearchParams({ range: "custom", ...definedParams(next.from, next.to) }, { replace: true })
  }

  return (
    <>
      <PageHeader
        eyebrow="Workout"
        title="History"
        actions={
          <Button variant="outline" className="h-10" onClick={() => navigate("/workout")}>
            Back to workout
          </Button>
        }
      />

      <div className="flex flex-col gap-3">
        <ToggleGroup type="single" variant="outline" spacing={0} value={preset} onValueChange={choosePreset} aria-label="Show workouts from" className="w-full sm:w-fit">
          {HISTORY_PRESETS.map((option) => (
            // Sized to the label first, then sharing what's left: equal-width items (flex-1)
            // squeeze "Past month" past its border, since the toggle's min-w-8 lets them shrink below the text.
            <ToggleGroupItem key={option} value={option} className="h-10 min-w-fit flex-auto px-2 sm:px-3">
              {SHORT_LABELS[option] ? (
                <>
                  <span className="sm:hidden">{SHORT_LABELS[option]}</span>
                  <span className="hidden sm:inline">{HISTORY_PRESET_LABELS[option]}</span>
                </>
              ) : (
                HISTORY_PRESET_LABELS[option]
              )}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>

        {preset === "custom" ? (
          <div className="flex flex-col gap-1.5">
            <div className="grid grid-cols-2 gap-2 sm:flex sm:items-end">
              <div className="flex min-w-0 flex-col gap-1.5">
                <Label htmlFor="history-from">From</Label>
                <Input id="history-from" type="date" className="h-10" max={dayKey(today)} value={custom.from ?? ""} aria-invalid={error !== null} onChange={(event) => setCustom("from", event.target.value)} />
              </div>
              <div className="flex min-w-0 flex-col gap-1.5">
                <Label htmlFor="history-to">To</Label>
                <Input id="history-to" type="date" className="h-10" max={dayKey(today)} value={custom.to ?? ""} aria-invalid={error !== null} onChange={(event) => setCustom("to", event.target.value)} />
              </div>
            </div>
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        ) : filtered && describeRange(range) ? (
          <p className="text-sm text-muted-foreground">{describeRange(range)}</p>
        ) : null}
      </div>

      {error ? null : history.isError && !workouts ? (
        <QueryError title="Couldn’t load your workouts" error={history.error} onRetry={() => void history.refetch()} retrying={history.isFetching} />
      ) : !workouts ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading workouts">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-20 w-full" />
          ))}
        </div>
      ) : workouts.length === 0 ? (
        <Empty className="border py-10">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <History />
            </EmptyMedia>
            <EmptyTitle>{filtered ? "No workouts in this period" : "No workouts yet"}</EmptyTitle>
            <EmptyDescription>{filtered ? "Try a longer period, or show everything." : "Finish a workout and it will show up here."}</EmptyDescription>
          </EmptyHeader>
          {filtered ? (
            <EmptyContent>
              <Button variant="outline" className="h-10" onClick={() => choosePreset("all")}>
                Show all
              </Button>
            </EmptyContent>
          ) : null}
        </Empty>
      ) : (
        <>
          <Card className="gap-0 overflow-hidden py-0">
            <ul className="divide-y">
              {workouts.map((workout) => (
                <HistoryRow key={workout.id} workout={workout} />
              ))}
            </ul>
          </Card>
          {history.isFetchNextPageError ? (
            <QueryError title="Couldn’t load more workouts" error={history.error} onRetry={() => void history.fetchNextPage()} retrying={history.isFetchingNextPage} />
          ) : null}
          {history.hasNextPage ? (
            <Button variant="outline" className="h-10 self-center" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>
              {history.isFetchingNextPage ? <Spinner data-icon="inline-start" /> : null}
              Load more
            </Button>
          ) : null}
        </>
      )}
    </>
  )
}

function definedParams(from: string | undefined, to: string | undefined) {
  return { ...(from ? { from } : {}), ...(to ? { to } : {}) }
}
