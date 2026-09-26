import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { amountLabelFor, MAX_AMOUNT, useServingAmount, type ServingAmount } from "@/hooks/use-serving-amount"
import { formatNumber } from "@/lib/format"
import type { Nutrition } from "@/lib/macros"
import { cn } from "@/lib/utils"
import { MEAL_LABELS, type Food, type FoodEntry, type MealType, type QuantityUnit } from "@/types/food"

const NUTRIENT_TILES = [
  { key: "calories", label: "kcal", dot: "bg-calories", unit: "" },
  { key: "protein", label: "Protein", dot: "bg-protein", unit: "g" },
  { key: "carbs", label: "Carbs", dot: "bg-carbs", unit: "g" },
  { key: "fat", label: "Fat", dot: "bg-fat", unit: "g" },
] as const

export function AmountFields({ food, amount, idPrefix }: { food: Food; amount: ServingAmount; idPrefix: string }) {
  const byWeightOnly = food.servingUnit === "g"
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_9rem] items-start gap-3">
      <TextField
        id={`${idPrefix}-amount`}
        label="Amount"
        inputMode="decimal"
        value={amount.amount}
        onChange={(event) => amount.setAmount(event.target.value)}
        error={amount.value !== undefined ? undefined : `Enter an amount between 0 and ${formatNumber(MAX_AMOUNT)}`}
      />
      <Field>
        <FieldLabel htmlFor={`${idPrefix}-unit`}>Unit</FieldLabel>
        <Select value={amount.unit} onValueChange={(value) => amount.changeUnit(value as QuantityUnit)}>
          <SelectTrigger id={`${idPrefix}-unit`} className="h-10 w-full">
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
  )
}

export function NutrientTiles({ nutrition }: { nutrition: Nutrition | null }) {
  return (
    <dl className="grid grid-cols-4 gap-2">
      {NUTRIENT_TILES.map((tile) => (
        <div key={tile.key} className="flex flex-col gap-1 rounded-lg border px-2.5 py-2">
          <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span aria-hidden className={cn("size-2 rounded-full", tile.dot)} />
            {tile.label}
          </dt>
          <dd className="font-display text-lg font-semibold">
            {nutrition ? `${formatNumber(nutrition[tile.key], tile.unit ? 1 : 0)}${tile.unit}` : "—"}
          </dd>
        </div>
      ))}
    </dl>
  )
}

type ServingEditorProps = {
  food: Food
  meal: MealType
  onAdd: (entry: Omit<FoodEntry, "id">) => void
  onCancel: () => void
}

/** Mount with `key={food.id}` so amount state resets per food without effects. */
export function ServingEditor({ food, meal, onAdd, onCancel }: ServingEditorProps) {
  const amount = useServingAmount(food)

  function handleAdd() {
    if (!amount.scaled || amount.value === undefined) return
    onAdd({
      meal,
      name: food.name,
      amountLabel: amountLabelFor(food, amount.value, amount.unit),
      source: food.source,
      ...amount.scaled,
      foodId: food.id,
      quantity: amount.value,
      quantityUnit: amount.unit,
    })
  }

  return (
    <section aria-label={`Amount of ${food.name}`} className="flex flex-col gap-4">
      <h3 className="truncate text-base font-medium">{food.name}</h3>
      <AmountFields food={food} amount={amount} idPrefix="serving" />
      <NutrientTiles nutrition={amount.scaled} />
      <div className="flex gap-2">
        <Button variant="outline" size="lg" className="h-10" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="lg" className="h-10 flex-1" disabled={!amount.scaled} onClick={handleAdd}>
          Add to {MEAL_LABELS[meal]}
        </Button>
      </div>
    </section>
  )
}
