import { format } from "date-fns"
import { CircleUser, Zap } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import { CaloriesWeekCard } from "@/components/home/calories-week-card"
import { CheckInBanner } from "@/components/home/check-in-banner"
import { PlannedWorkoutCard } from "@/components/home/planned-workout-card"
import { TodayNutritionCard } from "@/components/home/today-nutrition-card"
import { TodoCard } from "@/components/home/todo-card"
import { TrendWeightCard } from "@/components/home/trend-weight-card"
import { PageHeader } from "@/components/layout/page-header"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { WeighInForm } from "@/components/progress/weigh-in-form"
import { Button } from "@/components/ui/button"
import { useFoodLog } from "@/hooks/use-food-log"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { useAddWeighIn, useProgress } from "@/hooks/use-progress"
import { groupEntries } from "@/lib/food-log"
import { MEAL_TYPES, type MealType } from "@/types/food"

/** Meals whose usual time has passed: breakfast after 10:00, lunch after 15:00, dinner after 21:00. */
const MEAL_DEADLINES: Partial<Record<MealType, number>> = { breakfast: 10, lunch: 15, dinner: 21 }

export default function HomePage() {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const [today] = useState(() => new Date())
  const [weighInLayout, setWeighInLayout] = useState<OverlayLayout | null>(null)
  const [checkInDismissed, setCheckInDismissed] = useState(false)

  const progress = useProgress("1M")
  const foodLog = useFoodLog(today)
  const addWeighIn = useAddWeighIn()

  const todayKey = format(today, "yyyy-MM-dd")
  const points = progress.data?.weight.points
  const lastPoint = points?.[points.length - 1]
  const needsWeighIn = Boolean(points) && !(lastPoint?.date === todayKey && lastPoint.scaleKg != null)
  const lastWeightKg = points?.findLast((point) => point.scaleKg != null)?.scaleKg ?? undefined

  const byMeal = foodLog.data ? groupEntries(foodLog.data.entries).byMeal : undefined
  const hour = today.getHours()
  const missingMeal = byMeal ? MEAL_TYPES.find((meal) => (MEAL_DEADLINES[meal] ?? 24) <= hour && byMeal[meal].length === 0) : undefined

  function saveWeighIn(weightKg: number) {
    addWeighIn.mutate(
      { date: todayKey, weightKg },
      {
        onSuccess: () => {
          setWeighInLayout(null)
          toast.success("Weigh-in saved", { description: `${weightKg} kg added to your trend.` })
        },
        onError: (error) => toast.error("Couldn’t save your weigh-in", { description: apiErrorMessage(error) }),
      },
    )
  }

  const actionCards = (
    <>
      <CheckInBanner dismissed={checkInDismissed} onDismiss={() => setCheckInDismissed(true)} />
      <PlannedWorkoutCard />
      <TodoCard missingMeal={missingMeal} needsWeighIn={needsWeighIn} onAddWeighIn={() => setWeighInLayout(isDesktop ? "dialog" : "drawer")} />
    </>
  )

  return (
    <>
      <PageHeader
        eyebrow={format(today, "EEEE, d MMMM")}
        title="Today"
        actions={
          isDesktop ? (
            <Button className="h-10" asChild>
              <Link to="/workout?start=plan">
                <Zap data-icon="inline-start" />
                Start workout
              </Link>
            </Button>
          ) : (
            <Button variant="outline" size="icon-lg" className="size-11 rounded-full" asChild>
              <Link to="/profile" aria-label="Profile">
                <CircleUser />
              </Link>
            </Button>
          )
        }
      />

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-6">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-7 lg:gap-6">
          <TodayNutritionCard today={today} expenditureKcal={progress.data?.expenditureKcalPerDay} />
          {isDesktop ? <CaloriesWeekCard /> : actionCards}
        </div>
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-5 lg:gap-6">
          {isDesktop ? actionCards : null}
          <TrendWeightCard data={progress.data} error={progress.error} onRetry={() => void progress.refetch()} />
        </div>
      </div>

      <ResponsiveOverlay
        open={weighInLayout !== null}
        onOpenChange={(open) => (open ? undefined : setWeighInLayout(null))}
        layout={weighInLayout ?? "dialog"}
        title="Add weigh-in"
        description="Your trend weight smooths out daily swings from water and food."
      >
        <WeighInForm lastWeightKg={lastWeightKg} submitting={addWeighIn.isPending} onCancel={() => setWeighInLayout(null)} onSubmit={saveWeighIn} />
      </ResponsiveOverlay>
    </>
  )
}
