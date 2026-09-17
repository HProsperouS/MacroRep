import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"
import { MEAL_LABELS, MEAL_TYPES, type MealType } from "@/types/food"

type MealPickerProps = {
  value: MealType
  onChange: (meal: MealType) => void
  className?: string
}

export function MealPicker({ value, onChange, className }: MealPickerProps) {
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      spacing={0}
      value={value}
      // Radix emits "" when the active item is clicked again; keep a meal selected.
      onValueChange={(next) => (next ? onChange(next as MealType) : undefined)}
      aria-label="Meal"
      className={cn("w-full", className)}
    >
      {MEAL_TYPES.map((meal) => (
        <ToggleGroupItem key={meal} value={meal} className="h-10 flex-1">
          {MEAL_LABELS[meal]}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}
