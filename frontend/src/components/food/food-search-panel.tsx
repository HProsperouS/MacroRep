import { Barcode, Camera, Search, Zap } from "lucide-react"
import { useMemo, useState } from "react"

import { FormField } from "@/components/food/form-field"
import { MealPicker } from "@/components/food/meal-picker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { formatNumber, toNumber } from "@/lib/format"
import { scaleNutrition } from "@/lib/macros"
import { cn } from "@/lib/utils"
import { MEAL_LABELS, type Food, type FoodEntry, type MealType } from "@/types/food"

type AmountUnit = "serving" | "g"

type FoodSearchPanelProps = {
  foods: Food[]
  meal: MealType
  onMealChange: (meal: MealType) => void
  onAdd: (entry: Omit<FoodEntry, "id">) => void
  onQuickAdd: () => void
  onCreateCustom: (name?: string) => void
  onUnavailable: (feature: string) => void
  autoFocus?: boolean
  className?: string
}

function servingLabel(food: Food) {
  const weight = food.servingWeightG && food.servingUnit !== "g" ? ` · ${formatNumber(food.servingWeightG)} g` : ""
  return `${formatNumber(food.servingSize, 1)} ${food.servingUnit}${weight}`
}

function defaultAmount(food: Food): { amount: string; unit: AmountUnit } {
  return food.servingUnit === "g" ? { amount: String(food.servingSize), unit: "g" } : { amount: "1", unit: "serving" }
}

export function FoodSearchPanel({
  foods,
  meal,
  onMealChange,
  onAdd,
  onQuickAdd,
  onCreateCustom,
  onUnavailable,
  autoFocus,
  className,
}: FoodSearchPanelProps) {
  const [query, setQuery] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [amount, setAmount] = useState("1")
  const [unit, setUnit] = useState<AmountUnit>("serving")

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return foods.slice(0, 6)
    return foods.filter((food) => `${food.name} ${food.brand ?? ""}`.toLowerCase().includes(q)).slice(0, 8)
  }, [foods, query])

  const selected = foods.find((food) => food.id === selectedId) ?? null
  const amountValue = toNumber(amount)
  const amountValid = amountValue !== undefined && amountValue > 0 && amountValue <= 5000

  const scaled = useMemo(() => {
    if (!selected || !amountValid || amountValue === undefined) return null
    const factor =
      unit === "g" && selected.servingWeightG ? amountValue / selected.servingWeightG : amountValue / (selected.servingUnit === "g" ? selected.servingSize : 1)
    return scaleNutrition(selected.nutrition, factor)
  }, [selected, amountValid, amountValue, unit])

  function selectFood(food: Food) {
    const defaults = defaultAmount(food)
    setSelectedId(food.id)
    setAmount(defaults.amount)
    setUnit(defaults.unit)
  }

  function handleAdd() {
    if (!selected || !scaled || amountValue === undefined) return
    const amountLabel =
      unit === "g"
        ? `${formatNumber(amountValue, 1)} g`
        : `${formatNumber(amountValue * selected.servingSize, 1)} ${selected.servingUnit}${
            selected.servingWeightG ? ` · ${formatNumber(amountValue * selected.servingWeightG)} g` : ""
          }`
    onAdd({ meal, name: selected.name, amountLabel, source: selected.source, ...scaled })
    setSelectedId(null)
    setQuery("")
  }

  return (
    <section aria-label="Add food" className={cn("flex flex-col gap-4 rounded-2xl border bg-card p-4 sm:p-5", className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Add to {MEAL_LABELS[meal]}</h2>
      </div>

      <MealPicker value={meal} onChange={onMealChange} />

      <div className="relative">
        <Label htmlFor="food-search" className="sr-only">
          Search foods
        </Label>
        <Search className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          id="food-search"
          type="search"
          autoFocus={autoFocus}
          autoComplete="off"
          placeholder="Search foods, brands, dishes"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setSelectedId(null)
          }}
          className="h-12 rounded-xl bg-secondary pl-11 text-base dark:bg-secondary"
        />
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Button variant="outline" className="h-11 rounded-xl" onClick={() => onUnavailable("Barcode scanning")}>
          <Barcode /> Barcode
        </Button>
        <Button variant="outline" className="h-11 rounded-xl" onClick={() => onUnavailable("Meal photo scanning")}>
          <Camera /> Scan
        </Button>
        <Button variant="outline" className="h-11 rounded-xl" onClick={onQuickAdd}>
          <Zap /> Quick add
        </Button>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {query.trim() ? `${results.length} result${results.length === 1 ? "" : "s"}` : "Suggestions"}
        </p>

        {results.length === 0 ? (
          <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed p-4">
            <p className="text-sm">
              No foods match <span className="font-medium">“{query.trim()}”</span>.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" className="h-10" onClick={onQuickAdd}>
                <Zap /> Quick add
              </Button>
              <Button className="h-10" onClick={() => onCreateCustom(query.trim())}>
                Create “{query.trim()}”
              </Button>
            </div>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {results.map((food) => {
              const isSelected = food.id === selectedId
              return (
                <li key={food.id}>
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => (isSelected ? setSelectedId(null) : selectFood(food))}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition-colors outline-none hover:bg-secondary focus-visible:ring-3 focus-visible:ring-ring/50",
                      isSelected && "border-primary/50 bg-secondary",
                    )}
                  >
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium">{food.name}</span>
                        {food.source === "custom" && (
                          <Badge variant="outline" className="text-primary">
                            My food
                          </Badge>
                        )}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {food.brand ? `${food.brand} · ` : ""}
                        {servingLabel(food)}
                      </span>
                    </span>
                    <span className="shrink-0 whitespace-nowrap">
                      <span className="font-display text-lg font-semibold">{formatNumber(food.nutrition.calories)}</span>{" "}
                      <span className="text-xs text-muted-foreground">kcal</span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {selected && (
        <div className="flex flex-col gap-4 border-t pt-4">
          <p className="text-base font-semibold">{selected.name}</p>
          <div className="grid grid-cols-[1fr_9rem] gap-3">
            <FormField
              id="food-amount"
              label="Amount"
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              error={amountValid ? undefined : "Enter an amount above 0"}
            />
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="food-unit" className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                Unit
              </Label>
              <Select
                value={unit}
                onValueChange={(value) => {
                  const next = value as AmountUnit
                  if (next === unit) return
                  if (next === "g" && selected.servingWeightG) setAmount(String(selected.servingWeightG))
                  if (next === "serving") setAmount("1")
                  setUnit(next)
                }}
              >
                <SelectTrigger id="food-unit" className="h-11! w-full rounded-xl bg-secondary text-base dark:bg-secondary">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {selected.servingUnit !== "g" && (
                    <SelectItem value="serving">
                      {selected.servingSize} {selected.servingUnit}
                    </SelectItem>
                  )}
                  {selected.servingWeightG && <SelectItem value="g">grams</SelectItem>}
                </SelectContent>
              </Select>
            </div>
          </div>

          {scaled && (
            <dl className="grid grid-cols-4 gap-2">
              {[
                { label: "kcal", value: formatNumber(scaled.calories), dot: "bg-calories" },
                { label: "Protein", value: `${formatNumber(scaled.protein, 1)}g`, dot: "bg-protein" },
                { label: "Carbs", value: `${formatNumber(scaled.carbs, 1)}g`, dot: "bg-carbs" },
                { label: "Fat", value: `${formatNumber(scaled.fat, 1)}g`, dot: "bg-fat" },
              ].map((item) => (
                <div key={item.label} className="flex flex-col gap-1 rounded-xl bg-secondary p-2.5">
                  <dt className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span className={cn("size-2 rounded-full", item.dot)} aria-hidden />
                    {item.label}
                  </dt>
                  <dd className="font-display text-xl font-semibold">{item.value}</dd>
                </div>
              ))}
            </dl>
          )}

          <Button className="h-12 rounded-xl text-[15px] font-semibold" disabled={!scaled} onClick={handleAdd}>
            Add to {MEAL_LABELS[meal]}
          </Button>
        </div>
      )}
    </section>
  )
}
