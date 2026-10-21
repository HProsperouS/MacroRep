import { Camera, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { MealPicker } from "@/components/food/meal-picker"
import { Button } from "@/components/ui/button"
import { FieldLegend, FieldSet } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { TextField } from "@/components/ui/text-field"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesImplausiblyLow, implausibleCaloriesMessage, type Nutrition } from "@/lib/macros"
import { MEAL_LABELS, type MealType, type PhotoEstimate, type PhotoItem } from "@/types/food"

const NUTRIENTS = ["calories", "protein", "carbs", "fat"] as const
type Field = "name" | "grams" | (typeof NUTRIENTS)[number]

type Draft = Record<Field, string> & {
  key: number
  /** Values at `base.grams`: changing the amount scales the nutrition from these. */
  base: Nutrition & { grams: number }
}

function draftFrom(item: PhotoItem, key: number): Draft {
  return {
    key,
    name: item.name,
    grams: String(item.grams),
    calories: String(item.calories),
    protein: String(item.protein),
    carbs: String(item.carbs),
    fat: String(item.fat),
    base: item,
  }
}

const round1 = (value: number) => Math.round(value * 10) / 10

// What a food log entry accepts (the edit form's limits), and the estimate's own gram limit.
const MAX_NAME = 255
const MAX_GRAMS = 3_000
const MAX_CALORIES = 10_000
const MAX_MACRO_G = 1_000

/** The draft as a loggable item, or the first problem with each field. */
function check(draft: Draft): { item?: PhotoItem; errors: Partial<Record<Field, string>> } {
  const errors: Partial<Record<Field, string>> = {}
  const name = draft.name.trim()
  if (!name) errors.name = "Enter a name"
  else if (name.length > MAX_NAME) errors.name = `Keep it under ${MAX_NAME} characters`
  const grams = toNumber(draft.grams)
  if (grams === undefined || grams <= 0 || grams > MAX_GRAMS) errors.grams = `Between 0 and ${formatNumber(MAX_GRAMS)} g`
  const values: Partial<Nutrition> = {}
  for (const nutrient of NUTRIENTS) {
    const value = toNumber(draft[nutrient])
    const max = nutrient === "calories" ? MAX_CALORIES : MAX_MACRO_G
    if (value === undefined || value < 0 || value > max) errors[nutrient] = `0–${formatNumber(max)}`
    else if (nutrient === "calories" && !Number.isInteger(value)) errors.calories = "Whole kcal"
    else values[nutrient] = value
  }
  const nutrition = values as Nutrition
  if (!errors.calories && NUTRIENTS.every((n) => values[n] !== undefined) && caloriesImplausiblyLow(nutrition.calories, nutrition)) {
    errors.calories = implausibleCaloriesMessage(nutrition)
  }
  if (Object.keys(errors).length > 0 || grams === undefined) return { errors }
  return { item: { name, portion: `${formatNumber(grams, 1)} g`, grams, ...nutrition }, errors }
}

type PhotoReviewProps = {
  estimate: PhotoEstimate
  defaultMeal: MealType
  /** Logs the items in order; resolves with how many were logged before any failure. */
  onLog: (meal: MealType, items: PhotoItem[]) => Promise<number>
  onRetake: () => void
}

/** The model's estimate, for the user to correct before anything is logged (plan.md §7). */
export function PhotoReview({ estimate, defaultMeal, onLog, onRetake }: PhotoReviewProps) {
  const [meal, setMeal] = useState<MealType>(defaultMeal)
  const [drafts, setDrafts] = useState<Draft[]>(() => estimate.items.map(draftFrom))
  const [nextKey, setNextKey] = useState(estimate.items.length)
  const [logging, setLogging] = useState(false)

  const checked = drafts.map(check)
  const ready = checked.every((result) => result.item) && drafts.length > 0
  const total = checked.reduce((sum, result) => sum + (result.item?.calories ?? 0), 0)

  function change(key: number, field: Field, value: string) {
    setDrafts((current) =>
      current.map((draft) => {
        if (draft.key !== key) return draft
        const next = { ...draft, [field]: value }
        const grams = toNumber(value)
        if (field === "grams" && grams !== undefined && grams > 0 && draft.base.grams > 0) {
          // A new amount scales the nutrition last confirmed for the old one.
          const factor = grams / draft.base.grams
          next.calories = String(Math.round(draft.base.calories * factor))
          for (const macro of ["protein", "carbs", "fat"] as const) next[macro] = String(round1(draft.base[macro] * factor))
        } else if (field !== "name") {
          // A value typed in becomes what a later change of amount scales from.
          const values = NUTRIENTS.map((n) => toNumber(next[n]))
          const current = toNumber(next.grams)
          if (current !== undefined && current > 0 && values.every((v) => v !== undefined)) {
            const [calories, protein, carbs, fat] = values as number[]
            next.base = { grams: current, calories, protein, carbs, fat }
          }
        }
        return next
      }),
    )
  }

  function add() {
    setDrafts((current) => [...current, draftFrom({ name: "", portion: "", grams: 100, calories: 0, protein: 0, carbs: 0, fat: 0 }, nextKey)])
    setNextKey((key) => key + 1)
  }

  async function log() {
    const items = checked.map((result) => result.item as PhotoItem)
    setLogging(true)
    try {
      const logged = await onLog(meal, items)
      // Whatever was logged before a failure leaves the list, so trying again doesn't repeat it.
      // (After a full log the overlay closes; emptying it would flash as it fades.)
      if (logged < items.length) setDrafts((current) => current.slice(logged))
    } finally {
      setLogging(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {drafts.length === 0 ? (
        <p className="text-sm text-muted-foreground">{estimate.items.length === 0 ? "No food was found in this photo." : "Nothing left to log."}</p>
      ) : null}
      {estimate.note ? <p className="text-sm text-muted-foreground">{estimate.note}</p> : null}

      <FieldSet className="gap-2">
        <FieldLegend variant="label">Meal</FieldLegend>
        <MealPicker value={meal} onChange={setMeal} />
      </FieldSet>

      <ul className="flex flex-col gap-3">
        {drafts.map((draft, index) => {
          const { errors } = checked[index]
          const id = `photo-${draft.key}`
          return (
            <li key={draft.key} className="flex flex-col gap-3 rounded-lg border p-3" aria-label={draft.name.trim() || `Item ${index + 1}`}>
              <div className="flex items-end gap-2">
                <TextField id={`${id}-name`} label="Food" className="flex-1" value={draft.name} error={errors.name} disabled={logging} onChange={(e) => change(draft.key, "name", e.target.value)} />
                <Button variant="ghost" size="icon-lg" aria-label={`Remove ${draft.name.trim() || `item ${index + 1}`}`} disabled={logging} onClick={() => setDrafts((current) => current.filter((d) => d.key !== draft.key))}>
                  <Trash2 />
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                <TextField id={`${id}-grams`} label="Amount" unit="g" inputMode="decimal" value={draft.grams} error={errors.grams} disabled={logging} onChange={(e) => change(draft.key, "grams", e.target.value)} />
                <TextField id={`${id}-calories`} label="Calories" unit="kcal" inputMode="numeric" dotClassName="bg-calories" value={draft.calories} error={errors.calories} disabled={logging} onChange={(e) => change(draft.key, "calories", e.target.value)} />
                <TextField id={`${id}-protein`} label="Protein" unit="g" inputMode="decimal" dotClassName="bg-protein" value={draft.protein} error={errors.protein} disabled={logging} onChange={(e) => change(draft.key, "protein", e.target.value)} />
                <TextField id={`${id}-carbs`} label="Carbs" unit="g" inputMode="decimal" dotClassName="bg-carbs" value={draft.carbs} error={errors.carbs} disabled={logging} onChange={(e) => change(draft.key, "carbs", e.target.value)} />
                <TextField id={`${id}-fat`} label="Fat" unit="g" inputMode="decimal" dotClassName="bg-fat" value={draft.fat} error={errors.fat} disabled={logging} onChange={(e) => change(draft.key, "fat", e.target.value)} />
              </div>
            </li>
          )
        })}
      </ul>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" className="h-10" disabled={logging} onClick={add}>
          <Plus data-icon="inline-start" />
          Add an item
        </Button>
        <Button variant="ghost" className="h-10" disabled={logging} onClick={onRetake}>
          <Camera data-icon="inline-start" />
          Another photo
        </Button>
      </div>

      <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {drafts.length > 0 ? `${formatNumber(total)} kcal in all · estimates, check them first` : null}
        </p>
        <Button size="lg" className="h-11" disabled={!ready || logging} onClick={() => void log()}>
          {logging ? <Spinner data-icon="inline-start" /> : null}
          Log {drafts.length} item{drafts.length === 1 ? "" : "s"} to {MEAL_LABELS[meal]}
        </Button>
      </div>
    </div>
  )
}
