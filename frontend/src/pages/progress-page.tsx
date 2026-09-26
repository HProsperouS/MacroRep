import { format, parseISO } from "date-fns"
import { Download } from "lucide-react"
import { useMemo } from "react"
import { useSearchParams } from "react-router-dom"

import { TargetBarChart } from "@/components/charts/target-bar-chart"
import { WeightChart, WeightLegend } from "@/components/charts/weight-chart"
import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { Stat } from "@/components/layout/stat"
import { CheckInHistory } from "@/components/progress/check-in-history"
import { StrengthList } from "@/components/progress/strength-list"
import { WeighInList } from "@/components/progress/weigh-in-list"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useProgress } from "@/hooks/use-progress"
import { downloadCsv } from "@/lib/export-csv"
import { formatNumber, formatSigned } from "@/lib/format"
import { cn } from "@/lib/utils"
import { PROGRESS_RANGES, type ProgressRange, type ProgressResponse } from "@/types/progress"

function parseRange(value: string | null): ProgressRange {
  return PROGRESS_RANGES.find((range) => range === value) ?? "1M"
}

export default function ProgressPage() {
  // Range lives in the URL so it survives reloads and can be shared.
  const [searchParams, setSearchParams] = useSearchParams()
  const range = parseRange(searchParams.get("range"))
  const progress = useProgress(range)
  const data = progress.data

  function changeRange(next: string) {
    if (!next) return // Radix emits "" when the active item is clicked again.
    setSearchParams(next === "1M" ? {} : { range: next }, { replace: true })
  }

  function exportCsv(response: ProgressResponse) {
    downloadCsv(
      `macrorep-weight-${response.from}-to-${response.to}.csv`,
      ["date", "scale_kg", "trend_kg"],
      response.weight.points.map((point) => [point.date, point.scaleKg, point.trendKg]),
    )
  }

  return (
    <>
      <PageHeader
        eyebrow={data ? `${format(parseISO(data.from), "d MMMM")} – ${format(parseISO(data.to), "d MMMM")}` : "Loading period"}
        title="Progress"
        actions={
          <Button variant="outline" className="hidden h-10 sm:inline-flex" disabled={!data} onClick={() => (data ? exportCsv(data) : undefined)}>
            <Download data-icon="inline-start" />
            Export
          </Button>
        }
      />

      <ToggleGroup type="single" variant="outline" spacing={0} value={range} onValueChange={changeRange} aria-label="Time range" className="w-full sm:w-fit">
        {PROGRESS_RANGES.map((option) => (
          <ToggleGroupItem key={option} value={option} className="h-10 flex-1 sm:w-14">
            {option}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>

      {progress.isError && !data ? (
        <QueryError title="Couldn’t load your progress" error={progress.error} onRetry={() => void progress.refetch()} retrying={progress.isFetching} />
      ) : !data ? (
        <ProgressSkeleton />
      ) : (
        <div className={cn("flex flex-col gap-4 transition-opacity lg:gap-6", progress.isPlaceholderData && "opacity-60")} aria-busy={progress.isPlaceholderData || undefined}>
          <ProgressContent data={data} />
        </div>
      )}
    </>
  )
}

function ProgressContent({ data }: { data: ProgressResponse }) {
  const { weight, volume } = data
  const volumeData = useMemo(
    () =>
      volume.weeks.map((week) => ({
        key: week.weekStart,
        label: format(parseISO(week.weekStart), "d MMM"),
        tooltipTitle: `Week of ${format(parseISO(week.weekStart), "d MMM")}`,
        value: week.tonnes,
      })),
    [volume.weeks],
  )
  const onPace = data.weight.goalRatePerWeekKg < 0 ? weight.ratePerWeekKg <= weight.goalRatePerWeekKg * 0.8 : weight.ratePerWeekKg >= weight.goalRatePerWeekKg * 0.8
  // A real volume goal takes over the reference line once the backend provides one.
  const volumeReference =
    volume.targetTonnes != null ? { label: "Target", tonnes: volume.targetTonnes } : { label: "Average", tonnes: volume.averageTonnes }

  return (
    <>
      <Card>
        <CardContent className="grid grid-cols-2 gap-x-4 gap-y-5 md:grid-cols-3 xl:grid-cols-5">
          <Stat label="Trend weight" value={formatNumber(weight.currentTrendKg, 1)} unit="kg" hint={`${formatSigned(weight.changeKg)} kg this period`} />
          <Stat
            label="Rate"
            value={formatSigned(weight.ratePerWeekKg, 2)}
            unit="kg / wk"
            hint={
              <span className={onPace ? "text-primary" : "text-carbs"}>
                Goal {formatSigned(weight.goalRatePerWeekKg, 2)} kg / wk
              </span>
            }
          />
          <Stat label="Adherence" value={data.adherencePercent} unit="%" hint="Days within ±10% of target" />
          <Stat label="Workouts" value={`${data.workouts.done} / ${data.workouts.planned}`} hint="Planned sessions done" />
          <Stat
            label="Volume"
            value={formatNumber(volume.lastWeekTonnes, 1)}
            unit="t / wk"
            hint={volume.changePercent != null ? `Last full week · ${formatSigned(volume.changePercent, 0)}% vs prior` : "Last full week"}
          />
        </CardContent>
      </Card>

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-6">
        <Card className="lg:col-span-7">
          <CardHeader>
            <CardTitle>Weight</CardTitle>
            <CardAction>
              <WeightLegend />
            </CardAction>
          </CardHeader>
          <CardContent>
            {weight.points.some((point) => point.scaleKg != null) ? (
              <WeightChart points={weight.points} height={260} />
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">No weigh-ins in this period.</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader>
            <CardTitle>Weekly volume</CardTitle>
            <CardAction className="text-xs text-muted-foreground">
              {volumeReference.label} {formatNumber(volumeReference.tonnes)} t
            </CardAction>
          </CardHeader>
          <CardContent>
            <TargetBarChart
              data={volumeData}
              target={volumeReference.tonnes}
              targetLabel={volumeReference.label}
              seriesLabel="Volume"
              formatValue={(value) => `${formatNumber(value, 1)} t`}
              ariaLabel={`Weekly training volume in tonnes against a ${volumeReference.label.toLowerCase()} of ${volumeReference.tonnes} tonnes`}
              height={260}
            />
          </CardContent>
        </Card>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-2 lg:gap-6">
        <StrengthList lifts={data.strength} />
        <CheckInHistory items={data.checkIns} />
        <WeighInList from={data.from} to={data.to} />
      </div>
    </>
  )
}

function ProgressSkeleton() {
  return (
    <div className="flex flex-col gap-4 lg:gap-6" aria-busy="true" aria-label="Loading progress">
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-4 lg:grid-cols-12 lg:gap-6">
        <Skeleton className="h-80 lg:col-span-7" />
        <Skeleton className="h-80 lg:col-span-5" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2 lg:gap-6">
        <Skeleton className="h-56" />
        <Skeleton className="h-56" />
      </div>
    </div>
  )
}
