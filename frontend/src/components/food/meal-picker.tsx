import { cn } from "@/lib/utils"
import { MEAL_LABELS, MEAL_TYPES, type MealType } from "@/types/food"

type MealPickerProps = {
  value: MealType
  onChange: (meal: MealType) => void
  className?: string
}

export function MealPicker({ value, onChange, className }: MealPickerProps) {
  return (
    <div role="radiogroup" aria-label="Meal" className={cn("grid grid-cols-4 gap-1 rounded-xl border bg-secondary p-1", className)}>
      {MEAL_TYPES.map((meal) => {
        const selected = value === meal
        return (
          <button
            key={meal}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(meal)}
            className={cn(
              "h-9 rounded-lg text-[13px] font-medium text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50",
              selected && "bg-muted-foreground/20 text-foreground",
            )}
          >
            {MEAL_LABELS[meal]}
          </button>
        )
      })}
    </div>
  )
}
