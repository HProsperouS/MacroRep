import { Plus } from "lucide-react"

import { FoodRow } from "@/components/food/food-row"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatNumber } from "@/lib/format"
import { MEAL_LABELS, type FoodEntry, type MealType } from "@/types/food"

type MealSectionProps = {
  meal: MealType
  entries: FoodEntry[]
  onAdd: (meal: MealType) => void
  onRemove: (entryId: string) => void
}

export function MealSection({ meal, entries, onAdd, onRemove }: MealSectionProps) {
  const label = MEAL_LABELS[meal]
  const calories = entries.reduce((sum, entry) => sum + entry.calories, 0)
  const headingId = `meal-${meal}`

  return (
    <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl border bg-card">
      <header className="flex items-center justify-between gap-3 py-2.5 pr-2.5 pl-4 sm:pl-5">
        <div className="flex items-center gap-2.5">
          <h2 id={headingId} className="text-[15px] font-semibold">
            {label}
          </h2>
          {entries.length > 0 ? (
            <span className="text-sm text-muted-foreground">{formatNumber(calories)} kcal</span>
          ) : (
            <Badge variant="outline" className="h-6 text-carbs">
              Not logged
            </Badge>
          )}
        </div>
        <Button variant="outline" size="icon" className="size-10" aria-label={`Add food to ${label}`} onClick={() => onAdd(meal)}>
          <Plus />
        </Button>
      </header>
      {entries.length > 0 && (
        <ul>
          {entries.map((entry) => (
            <FoodRow key={entry.id} entry={entry} onRemove={onRemove} />
          ))}
        </ul>
      )}
    </section>
  )
}
