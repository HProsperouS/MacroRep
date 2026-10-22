import { format, parseISO } from "date-fns"

import { QueryError } from "@/components/layout/query-error"
import { Skeleton } from "@/components/ui/skeleton"
import { useTargetHistory } from "@/hooks/use-profile"
import { formatNumber } from "@/lib/format"
import type { TargetSource } from "@/types/food"

const SOURCE_LABELS: Record<TargetSource, string> = {
  initial: "Starting targets",
  manual: "Set by you",
  "check-in": "From a check-in",
}

/** The latest versions of the daily targets, newest first, so past days can be read against what applied then. */
export function TargetHistory() {
  const history = useTargetHistory()

  if (history.isError) {
    return <QueryError title="Couldn’t load the target history" error={history.error} onRetry={() => void history.refetch()} retrying={history.isFetching} />
  }
  if (!history.data) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading target history">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  return (
    <ol className="-mx-2 flex max-h-72 flex-col divide-y overflow-y-auto" aria-label="Target history">
      {history.data.map((entry, index) => (
        <li key={entry.version} className="flex items-baseline justify-between gap-3 px-2 py-2 text-sm">
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="font-medium tabular-nums">
              {formatNumber(entry.calories)} kcal
              {index === 0 ? <span className="ml-2 text-xs font-normal text-primary">Current</span> : null}
            </span>
            <span className="truncate text-muted-foreground tabular-nums">
              P {formatNumber(entry.protein)} g · C {formatNumber(entry.carbs)} g · F {formatNumber(entry.fat)} g
            </span>
          </span>
          <span className="flex shrink-0 flex-col items-end gap-0.5 text-right">
            <span className="tabular-nums">From {format(parseISO(entry.effectiveDate), "d MMM yyyy")}</span>
            <span className="text-xs text-muted-foreground">{SOURCE_LABELS[entry.source]}</span>
          </span>
        </li>
      ))}
    </ol>
  )
}
