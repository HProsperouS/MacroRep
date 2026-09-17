import { useState } from "react"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { formatNumber, toNumber } from "@/lib/format"
import { scaleNutrition, type Nutrition } from "@/lib/macros"
import { cn } from "@/lib/utils"
import { MEAL_LABELS, type Food, type FoodEntry, type MealType } from "@/types/food"

type AmountUnit = "serving" | "g"

const NUTRIENT_TILES = [
  { key: "calories", label: "kcal", dot: "bg-calories", unit: "" },
  { key: "protein", label: "Protein", dot: "bg-protein", unit: "g" },
  { key: "carbs", label: "Carbs", dot: "bg-carbs", unit: "g" },
  { key: "fat", label: "Fat", dot: "bg-fat", unit: "g" },
] as const

type ServingEditorProps = {
  food: Food
  meal: MealType
  onAdd: (entry: Omit<FoodEntry, "id">) => void
  onCancel: () => void
}

/** Mount with `key={food.id}` so amount state resets per food without effects. */
export function ServingEditor({ food, meal, onAdd, onCancel }: ServingEditorProps) {
  const byWeightOnly = food.servingUnit === "g"
  const [unit, setUnit] = useState<AmountUnit>(byWeightOnly ? "g" : "serving")
  const [amount, setAmount] = useState(() => (byWeightOnly ? String(food.servingSize) : "1"))

  const amountValue = toNumber(amount)
  const valid = amountValue !== undefined && amountValue > 0 && amountValue <= 5000

  const scaled: Nutrition | null = valid
    ? scaleNutrition(food.nutrition, unit === "g" ? amountValue / (food.servingWeightG ?? food.servingSize) : amountValue)
    : null

  function changeUnit(next: AmountUnit) {
    if (next === unit) return
    setAmount(next === "g" ? String(food.servingWeightG ?? 100) : "1")
    setUnit(next)
  }

  function handleAdd() {
    if (!scaled || amountValue === undefined) return
    const amountLabel =
      unit === "g"
        ? `${formatNumber(amountValue, 1)} g`
        : `${formatNumber(amountValue * food.servingSize, 1)} ${food.servingUnit}${
            food.servingWeightG ? ` · ${formatNumber(amountValue * food.servingWeightG)} g` : ""
          }`
    onAdd({ meal, name: food.name, amountLabel, source: food.source, ...scaled })
  }

  return (
    <section aria-label={`Amount of ${food.name}`} className="flex flex-col gap-4">
      <h3 className="truncate text-base font-medium">{food.name}</h3>

      <div className="grid grid-cols-[minmax(0,1fr)_9rem] items-start gap-3">
        <TextField
          id="serving-amount"
          label="Amount"
          inputMode="decimal"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          error={valid ? undefined : "Enter an amount between 0 and 5,000"}
        />
        <Field>
          <FieldLabel htmlFor="serving-unit">Unit</FieldLabel>
          <Select value={unit} onValueChange={(value) => changeUnit(value as AmountUnit)}>
            <SelectTrigger id="serving-unit" className="h-10 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {byWeightOnly ? null : (
                  <SelectItem value="serving">
                    {formatNumber(food.servingSize, 1)} {food.servingUnit}
                  </SelectItem>
                )}
                {food.servingWeightG != null || byWeightOnly ? <SelectItem value="g">grams</SelectItem> : null}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
      </div>

      <dl className="grid grid-cols-4 gap-2">
        {NUTRIENT_TILES.map((tile) => (
          <div key={tile.key} className="flex flex-col gap-1 rounded-lg border px-2.5 py-2">
            <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span aria-hidden className={cn("size-2 rounded-full", tile.dot)} />
              {tile.label}
            </dt>
            <dd className="font-display text-lg font-semibold">
              {scaled ? `${formatNumber(scaled[tile.key], tile.unit ? 1 : 0)}${tile.unit}` : "—"}
            </dd>
          </div>
        ))}
      </dl>

      <div className="flex gap-2">
        <Button variant="outline" size="lg" className="h-10" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="lg" className="h-10 flex-1" disabled={!scaled} onClick={handleAdd}>
          Add to {MEAL_LABELS[meal]}
        </Button>
      </div>
    </section>
  )
}
