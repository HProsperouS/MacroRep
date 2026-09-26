import { format, parseISO, subDays } from "date-fns"
import { Pencil, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { QueryError } from "@/components/layout/query-error"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { WeighInForm } from "@/components/progress/weigh-in-form"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { useAddWeighIn, useDeleteWeighIn, useUpdateWeighIn, useWeighIns } from "@/hooks/use-progress"
import { toDayKey } from "@/lib/dates"
import { formatNumber } from "@/lib/format"
import type { WeighIn, WeighInInput } from "@/types/progress"

/** The API serves at most this many days per request. */
const MAX_DAYS = 366

type WeighInListProps = {
  /** yyyy-MM-dd bounds of the selected progress range. */
  from: string
  to: string
  className?: string
}

export function WeighInList({ from, to, className }: WeighInListProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const earliest = toDayKey(subDays(parseISO(to), MAX_DAYS - 1))
  const clamped = from < earliest
  const weighIns = useWeighIns(clamped ? earliest : from, to)
  const update = useUpdateWeighIn()
  const remove = useDeleteWeighIn()
  const restore = useAddWeighIn()
  const [editing, setEditing] = useState<{ weighIn: WeighIn; layout: OverlayLayout } | null>(null)

  function saveEdit(values: WeighInInput) {
    if (!editing) return
    const { weighIn } = editing
    const input = {
      ...(values.date !== weighIn.date && { date: values.date }),
      ...(values.weightKg !== weighIn.weightKg && { weightKg: values.weightKg }),
    }
    if (Object.keys(input).length === 0) {
      setEditing(null)
      return
    }
    update.mutate(
      { weighInId: weighIn.id, input },
      {
        onSuccess: () => {
          setEditing(null)
          toast.success("Weigh-in updated", { description: `${formatNumber(values.weightKg, 1)} kg on ${dayLabel(values.date)}` })
        },
        onError: (error) => toast.error("Couldn’t update that weigh-in", { description: apiErrorMessage(error) }),
      },
    )
  }

  function deleteWeighIn(weighIn: WeighIn) {
    remove.mutate(weighIn.id, {
      onSuccess: () =>
        toast("Weigh-in deleted", {
          description: `${formatNumber(weighIn.weightKg, 1)} kg on ${dayLabel(weighIn.date)}`,
          action: { label: "Undo", onClick: () => restore.mutate({ date: weighIn.date, weightKg: weighIn.weightKg }) },
        }),
      onError: (error) => toast.error("Couldn’t delete that weigh-in", { description: apiErrorMessage(error) }),
    })
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Weigh-ins</CardTitle>
        {clamped ? <CardDescription>Latest 12 months</CardDescription> : null}
        {weighIns.data ? <CardAction className="text-xs text-muted-foreground">{weighIns.data.length} logged</CardAction> : null}
      </CardHeader>
      <CardContent>
        {weighIns.isPending ? (
          <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading weigh-ins">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : weighIns.isError ? (
          <QueryError title="Couldn’t load your weigh-ins" error={weighIns.error} onRetry={() => void weighIns.refetch()} retrying={weighIns.isFetching} />
        ) : weighIns.data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No weigh-ins in this period.</p>
        ) : (
          <ul className="-mx-2 max-h-96 divide-y overflow-y-auto">
            {weighIns.data.map((weighIn) => {
              const deleting = remove.isPending && remove.variables === weighIn.id
              return (
                <li key={weighIn.id} className="flex items-center gap-3 px-2 py-1.5" aria-busy={deleting || undefined}>
                  <span className="min-w-0 flex-1 truncate text-sm">{dayLabel(weighIn.date)}</span>
                  <span className="flex shrink-0 items-baseline gap-2">
                    <span className="font-display text-lg leading-none font-semibold">{formatNumber(weighIn.weightKg, 1)}</span>
                    <span className="text-xs text-muted-foreground">kg · trend {formatNumber(weighIn.trendKg, 1)}</span>
                  </span>
                  <span className="flex shrink-0">
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      className="text-muted-foreground"
                      aria-label={`Edit weigh-in on ${dayLabel(weighIn.date)}`}
                      disabled={deleting}
                      onClick={() => setEditing({ weighIn, layout: isDesktop ? "dialog" : "drawer" })}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-lg"
                      className="text-muted-foreground"
                      aria-label={`Delete weigh-in on ${dayLabel(weighIn.date)}`}
                      disabled={deleting}
                      onClick={() => deleteWeighIn(weighIn)}
                    >
                      <Trash2 />
                    </Button>
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>

      <ResponsiveOverlay
        open={editing !== null}
        onOpenChange={(open) => (open ? undefined : setEditing(null))}
        layout={editing?.layout ?? "dialog"}
        title="Edit weigh-in"
        description="Fix the weight, or move it to the day it was actually taken."
      >
        {editing ? (
          <WeighInForm
            key={editing.weighIn.id}
            initial={{ date: editing.weighIn.date, weightKg: editing.weighIn.weightKg }}
            submitting={update.isPending}
            submitLabel="Save changes"
            onCancel={() => setEditing(null)}
            onSubmit={saveEdit}
          />
        ) : null}
      </ResponsiveOverlay>
    </Card>
  )
}

function dayLabel(day: string) {
  return format(parseISO(day), "EEE d MMM yyyy")
}
