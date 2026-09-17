import { Scale, TriangleAlert } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { MEAL_LABELS, type MealType } from "@/types/food"

type TodoCardProps = {
  missingMeal?: MealType
  needsWeighIn: boolean
  onAddWeighIn: () => void
}

/** Nudges for today. Renders nothing when there is nothing to do. */
export function TodoCard({ missingMeal, needsWeighIn, onAddWeighIn }: TodoCardProps) {
  if (!missingMeal && !needsWeighIn) return null

  return (
    <Card size="sm">
      <CardContent>
        <ul className="divide-y">
          {missingMeal ? (
            <li className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
              <TriangleAlert className="size-5 shrink-0 text-carbs" aria-hidden />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-sm font-medium">{MEAL_LABELS[missingMeal]} not logged</span>
                <span className="text-xs text-muted-foreground">Log it now so today’s totals stay accurate</span>
              </div>
              <Button variant="outline" className="h-9" asChild>
                <Link to="/food" aria-label={`Log ${MEAL_LABELS[missingMeal]}`}>
                  Log
                </Link>
              </Button>
            </li>
          ) : null}
          {needsWeighIn ? (
            <li className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
              <Scale className="size-5 shrink-0 text-protein" aria-hidden />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="text-sm font-medium">No weigh-in today</span>
                <span className="text-xs text-muted-foreground">Morning weigh-ins keep the trend accurate</span>
              </div>
              <Button variant="outline" className="h-9" onClick={onAddWeighIn} aria-label="Add today’s weigh-in">
                Add
              </Button>
            </li>
          ) : null}
        </ul>
      </CardContent>
    </Card>
  )
}
