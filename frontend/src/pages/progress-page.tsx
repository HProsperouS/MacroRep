import { format, parseISO } from "date-fns"
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
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useProgress } from "@/hooks/use-progress"
import { formatNumber, formatSigned } from "@/lib/format"
import { cn } from "@/lib/utils"
import { PROGRESS_RANGES, type ProgressRange, type ProgressResponse } from "@/types/progress"

/** When maintaining, a weekly change within this much either way is holding steady. */
const MAINTAIN_TOLERANCE_KG = 0.25

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

  return (
    <>
      <PageHeader
        eyebrow={data ? `${format(parseISO(data.from), "d MMMM")} – ${format(parseISO(data.to), "d MMMM")}` : "Loading period"}
        title="Progress"
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
  const { weight, volume, logging, rpe } = data
  const loggedDays = logging.completeDays + logging.partialDays
  // Partial days count as eaten, so a light week shows as a real shortfall.
  const avgGapKcal = loggedDays > 0 ? logging.targetGapKcal / loggedDays : null
  const volumeData = useMemo(
    () =>
      volume.weeks.map((week) => ({
        key: week.weekStart,
        label: format(parseISO(week.weekStart), "d MMM"),
        tooltipTitle: `Week of ${format(parseISO(week.weekStart), "d MMM")}`,
        value: week.tonnes,
        note: week.avgRpe != null ? `Avg RPE ${formatNumber(week.avgRpe, 1)}` : undefined,
      })),
    [volume.weeks],
  )
  const rate = weight.ratePerWeekKg
  const goalRate = weight.goalRatePerWeekKg
  // Null with no rate yet: then neither on pace nor behind. Holding steady allows a little either way.
  const onPace =
    rate == null ? null : goalRate === 0 ? Math.abs(rate) <= MAINTAIN_TOLERANCE_KG : goalRate < 0 ? rate <= goalRate * 0.8 : rate >= goalRate * 0.8

  return (
    <>
      <Card>
        <CardContent className="grid grid-cols-2 gap-x-4 gap-y-5 md:grid-cols-4">
          <Stat label="Trend weight" value={weight.currentTrendKg == null ? "—" : formatNumber(weight.currentTrendKg, 1)} unit="kg" hint={`${formatSigned(weight.changeKg)} kg this period`} />
          <Stat
            label="Rate"
            value={rate == null ? "—" : formatSigned(rate, 2)}
            unit={rate == null ? undefined : "kg / wk"}
            hint={
              onPace == null ? (
                "Needs a week of weigh-ins"
              ) : (
                <span className={onPace ? "text-primary" : "text-carbs"}>{goalRate === 0 ? "Goal: hold steady" : `Goal ${formatSigned(goalRate, 2)} kg / wk`}</span>
              )
            }
          />
          <Stat
            label="Days logged"
            value={data.adherencePercent ?? "—"}
            unit={data.adherencePercent != null ? "%" : undefined}
            hint={`${logging.completeDays} complete · ${logging.partialDays} under half target`}
          />
          <Stat
            label="On target"
            value={logging.targetAdherencePercent ?? "—"}
            unit={logging.targetAdherencePercent != null ? "%" : undefined}
            hint={avgGapKcal != null ? `${formatSigned(avgGapKcal, 0)} kcal / logged day vs target` : "Logged days within ±10%"}
          />
          <Stat
            label="Workouts"
            value={`${data.workouts.done} / ${data.workouts.planned}`}
            hint={data.workouts.completionPercent != null ? `${formatNumber(data.workouts.completionPercent, 0)}% of planned` : "Nothing planned yet"}
          />
          <Stat
            label="Volume"
            value={formatNumber(volume.lastWeekTonnes, 1)}
            unit="t / wk"
            hint={volume.changePercent != null ? `Last full week · ${formatSigned(volume.changePercent, 0)}% vs prior` : "Last full week"}
          />
          <Stat
            label="Avg RPE"
            value={rpe.thisWeekAvg != null ? formatNumber(rpe.thisWeekAvg, 1) : "—"}
            hint={rpe.thisWeekAvg == null ? "No RPE logged this week yet" : rpe.change != null ? `This week · ${formatSigned(rpe.change, 1)} vs last week` : "This week"}
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
              Average {formatNumber(volume.averageTonnes)} t
            </CardAction>
          </CardHeader>
          <CardContent>
            <TargetBarChart
              data={volumeData}
              target={volume.averageTonnes}
              targetLabel="Average"
              seriesLabel="Volume"
              formatValue={(value) => `${formatNumber(value, 1)} t`}
              ariaLabel={`Weekly training volume in tonnes against an average of ${volume.averageTonnes} tonnes`}
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
