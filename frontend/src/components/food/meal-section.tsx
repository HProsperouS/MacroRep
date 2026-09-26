import { Plus } from "lucide-react"

import { FoodRow } from "@/components/food/food-row"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatNumber } from "@/lib/format"
import { MEAL_LABELS, type FoodEntry, type MealType } from "@/types/food"

type MealSectionProps = {
  meal: MealType
  entries: FoodEntry[]
  onAdd: (meal: MealType) => void
  onEdit: (entry: FoodEntry) => void
  onRemove: (entryId: string) => void
}

export function MealSection({ meal, entries, onAdd, onEdit, onRemove }: MealSectionProps) {
  const label = MEAL_LABELS[meal]
  const calories = entries.reduce((sum, entry) => sum + entry.calories, 0)

  return (
    <Card size="sm" className="gap-0 pb-0">
      <CardHeader className="pb-3">
        <CardTitle>{label}</CardTitle>
        <CardDescription>
          {entries.length > 0 ? (
            `${formatNumber(calories)} kcal · ${entries.length} item${entries.length === 1 ? "" : "s"}`
          ) : (
            <Badge variant="outline">Not logged</Badge>
          )}
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="icon-lg" aria-label={`Add food to ${label}`} onClick={() => onAdd(meal)}>
            <Plus />
          </Button>
        </CardAction>
      </CardHeader>
      {entries.length > 0 ? (
        <CardContent className="border-t px-0">
          <ul className="divide-y">
            {entries.map((entry) => (
              <FoodRow key={entry.id} entry={entry} onEdit={onEdit} onRemove={onRemove} />
            ))}
          </ul>
        </CardContent>
      ) : (
        <div className="pb-3" />
      )}
    </Card>
  )
}

export function MealSectionSkeleton() {
  return (
    <Card size="sm" aria-busy="true">
      <CardHeader>
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-3 w-28" />
        <CardAction>
          <Skeleton className="size-9" />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </CardContent>
    </Card>
  )
}
