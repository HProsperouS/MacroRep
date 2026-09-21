import { ChevronRight, Dumbbell, Pencil } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { PageHeader } from "@/components/layout/page-header"
import { QueryError } from "@/components/layout/query-error"
import { PlanDayEditor } from "@/components/workout/plan-day-editor"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useDeletePlanDay, useSavePlanDay, useWeekPlan } from "@/hooks/use-workout"
import { WEEKDAY_LABELS } from "@/types/workout"

export default function WorkoutPlanPage() {
  const navigate = useNavigate()
  const plan = useWeekPlan()
  const savePlanDay = useSavePlanDay()
  const deletePlanDay = useDeletePlanDay()
  const [editingDay, setEditingDay] = useState<number | null>(null)

  if (editingDay !== null) {
    const day = plan.data?.find((entry) => entry.dayOfWeek === editingDay)
    return (
      <>
        <PageHeader eyebrow="Weekly plan" title={`Edit ${WEEKDAY_LABELS[editingDay]}`} />
        <PlanDayEditor
          dayLabel={WEEKDAY_LABELS[editingDay]}
          plan={day?.plan ?? null}
          submitting={savePlanDay.isPending}
          deleting={deletePlanDay.isPending}
          onSave={(input) =>
            savePlanDay.mutate(
              { dayOfWeek: editingDay, input },
              {
                onSuccess: () => {
                  toast.success(`${WEEKDAY_LABELS[editingDay]} saved`)
                  setEditingDay(null)
                },
                onError: (error) => toast.error("Couldn’t save this day", { description: apiErrorMessage(error) }),
              },
            )
          }
          onClearDay={() =>
            deletePlanDay.mutate(editingDay, {
              onSuccess: () => {
                toast.success(`${WEEKDAY_LABELS[editingDay]} cleared to a rest day`)
                setEditingDay(null)
              },
              onError: (error) => toast.error("Couldn’t clear this day", { description: apiErrorMessage(error) }),
            })
          }
          onCancel={() => setEditingDay(null)}
        />
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Workout"
        title="Weekly plan"
        actions={
          <Button variant="outline" className="h-10" onClick={() => navigate("/workout")}>
            Back to workout
          </Button>
        }
      />

      {plan.isError ? (
        <QueryError title="Couldn’t load your plan" error={plan.error} onRetry={() => void plan.refetch()} retrying={plan.isFetching} />
      ) : plan.data ? (
        <div className="flex flex-col gap-2">
          {plan.data.map((day) => (
            <Card key={day.dayOfWeek}>
              <CardContent className="flex items-center gap-3 py-1">
                <span className="flex size-11 shrink-0 items-center justify-center rounded-lg border bg-muted text-muted-foreground" aria-hidden>
                  <Dumbbell className="size-5" />
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-sm font-medium">{WEEKDAY_LABELS[day.dayOfWeek]}</span>
                  <span className="truncate text-sm text-muted-foreground">
                    {day.plan ? `${day.plan.name} · ${day.plan.exercises.length} exercise${day.plan.exercises.length === 1 ? "" : "s"}` : "Rest day"}
                  </span>
                </div>
                <Button variant="ghost" className="h-10" onClick={() => setEditingDay(day.dayOfWeek)}>
                  <Pencil data-icon="inline-start" />
                  Edit
                  <ChevronRight className="ml-1 size-4" aria-hidden />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading plan">
          {Array.from({ length: 7 }, (_, index) => (
            <Skeleton key={index} className="h-16 w-full" />
          ))}
        </div>
      )}
    </>
  )
}
