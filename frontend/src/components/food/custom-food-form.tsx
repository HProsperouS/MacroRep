import { zodResolver } from "@hookform/resolvers/zod"
import { Check, ChevronDown, TriangleAlert, UtensilsCrossed } from "lucide-react"
import { useState } from "react"
import { Controller, useForm, useWatch } from "react-hook-form"
import { z } from "zod"

import { CalorieRing } from "@/components/charts/calorie-ring"
import { MacroBar } from "@/components/charts/macro-bar"
import { FormField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesFromMacros, caloriesMismatch, energySplit } from "@/lib/macros"
import { cn } from "@/lib/utils"
import { MEAL_LABELS, MEAL_TYPES, SERVING_UNITS, type DailyTargets, type Food, type MealType } from "@/types/food"
import type { QuickAddDraft } from "@/components/food/quick-add-form"

const toNumberOrNaN = (value: unknown) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN)

const requiredAmount = (max: number, min = 0) =>
  z.preprocess(
    toNumberOrNaN,
    z
      .number({ required_error: "Required", invalid_type_error: "Enter a number" })
      .min(min, min > 0 ? "Must be above 0" : "Can’t be negative")
      .max(max, "That looks too high"),
  )

const optionalAmount = (max: number) =>
  z.preprocess(
    toNumberOrNaN,
    z.number({ invalid_type_error: "Enter a number" }).min(0, "Can’t be negative").max(max, "That looks too high").optional(),
  )

const customFoodSchema = z.object({
  name: z.string().trim().min(1, "Give the food a name").max(60, "Keep it under 60 characters"),
  brand: z.string().trim().max(60, "Keep it under 60 characters"),
  servingSize: requiredAmount(5_000, 0.01),
  servingUnit: z.enum(SERVING_UNITS),
  servingWeightG: optionalAmount(5_000),
  calories: requiredAmount(10_000),
  protein: requiredAmount(1_000),
  carbs: requiredAmount(1_000),
  fat: requiredAmount(1_000),
  fibreG: optionalAmount(500),
  sugarG: optionalAmount(1_000),
  sodiumMg: optionalAmount(50_000),
  meal: z.enum(MEAL_TYPES),
})

type CustomFoodInput = z.input<typeof customFoodSchema>
type CustomFoodValues = z.output<typeof customFoodSchema>

export type CustomFoodSubmit = {
  food: Omit<Food, "id" | "source">
  logTo: MealType | null
}

type CustomFoodFormProps = {
  defaultMeal: MealType
  draft?: QuickAddDraft
  targets: DailyTargets
  onSubmit: (result: CustomFoodSubmit) => void
}

const str = (value: number | undefined) => (value === undefined ? "" : String(value))

export function CustomFoodForm({ defaultMeal, draft, targets, onSubmit }: CustomFoodFormProps) {
  const [showMore, setShowMore] = useState(false)
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CustomFoodInput, unknown, CustomFoodValues>({
    resolver: zodResolver(customFoodSchema),
    defaultValues: {
      name: draft?.name ?? "",
      brand: "",
      servingSize: "1",
      servingUnit: "piece",
      servingWeightG: "",
      calories: str(draft?.calories),
      protein: str(draft?.protein),
      carbs: str(draft?.carbs),
      fat: str(draft?.fat),
      fibreG: "",
      sugarG: "",
      sodiumMg: "",
      meal: defaultMeal,
    },
  })

  const watched = useWatch({ control })
  const name = (watched.name as string | undefined)?.trim() || "Untitled food"
  const calories = toNumber(watched.calories) ?? 0
  const macros = { protein: toNumber(watched.protein) ?? 0, carbs: toNumber(watched.carbs) ?? 0, fat: toNumber(watched.fat) ?? 0 }
  const computed = caloriesFromMacros(macros)
  const split = energySplit(macros)
  const servingSize = toNumber(watched.servingSize)
  const servingUnit = (watched.servingUnit as string | undefined) ?? "piece"
  const weight = toNumber(watched.servingWeightG)
  const per100 = weight && weight > 0 ? 100 / weight : undefined
  const hasEnergy = calories > 0 && computed > 0
  const mismatch = hasEnergy && caloriesMismatch(calories, macros)
  const logMeal = (watched.meal as MealType | undefined) ?? defaultMeal

  const toResult = (values: CustomFoodValues, logTo: MealType | null): CustomFoodSubmit => ({
    food: {
      name: values.name,
      brand: values.brand || undefined,
      servingSize: values.servingSize,
      servingUnit: values.servingUnit,
      servingWeightG: values.servingUnit === "g" ? values.servingSize : values.servingWeightG,
      nutrition: { calories: values.calories, protein: values.protein, carbs: values.carbs, fat: values.fat },
      fibreG: values.fibreG,
      sugarG: values.sugarG,
      sodiumMg: values.sodiumMg,
    },
    logTo,
  })

  const saveOnly = handleSubmit((values) => onSubmit(toResult(values, null)))
  const saveAndLog = handleSubmit((values) => onSubmit(toResult(values, values.meal)))

  return (
    <form onSubmit={saveAndLog} noValidate className="grid gap-6 lg:grid-cols-12">
      <div className="flex flex-col gap-4 lg:col-span-7">
        <FormField id="cf-name" label="Food name" placeholder="e.g. Mum’s fried rice" error={errors.name?.message} {...register("name")} />

        <div className="grid gap-3 sm:grid-cols-2">
          <FormField id="cf-brand" label="Brand or place (optional)" placeholder="e.g. Koufu" error={errors.brand?.message} {...register("brand")} />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cf-meal" className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
              Log to
            </Label>
            <Controller
              control={control}
              name="meal"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="cf-meal" className="h-11! w-full rounded-xl bg-secondary text-base dark:bg-secondary">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MEAL_TYPES.map((meal) => (
                      <SelectItem key={meal} value={meal}>
                        {MEAL_LABELS[meal]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <FormField id="cf-serving" label="Serving" inputMode="decimal" error={errors.servingSize?.message} {...register("servingSize")} />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cf-unit" className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
              Unit
            </Label>
            <Controller
              control={control}
              name="servingUnit"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="cf-unit" className="h-11! w-full rounded-xl bg-secondary text-base dark:bg-secondary">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SERVING_UNITS.map((unit) => (
                      <SelectItem key={unit} value={unit}>
                        {unit}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <FormField
            id="cf-weight"
            label="Weight"
            suffix="g"
            inputMode="decimal"
            placeholder="—"
            disabled={servingUnit === "g"}
            error={errors.servingWeightG?.message}
            {...register("servingWeightG")}
          />
        </div>

        <div className="h-px bg-border" />
        <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Nutrition per serving</p>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <FormField id="cf-calories" label="Calories" suffix="kcal" inputMode="decimal" placeholder="0" dotClassName="bg-calories" error={errors.calories?.message} {...register("calories")} />
          <FormField id="cf-protein" label="Protein" suffix="g" inputMode="decimal" placeholder="0" dotClassName="bg-protein" error={errors.protein?.message} {...register("protein")} />
          <FormField id="cf-carbs" label="Carbs" suffix="g" inputMode="decimal" placeholder="0" dotClassName="bg-carbs" error={errors.carbs?.message} {...register("carbs")} />
          <FormField id="cf-fat" label="Fat" suffix="g" inputMode="decimal" placeholder="0" dotClassName="bg-fat" error={errors.fat?.message} {...register("fat")} />
        </div>

        {hasEnergy &&
          (mismatch ? (
            <p role="status" className="flex items-start gap-2 text-[13px] text-carbs">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              Macros add up to {formatNumber(computed)} kcal — check the label for alcohol or fibre.
            </p>
          ) : (
            <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
              <Check className="size-4 text-primary" aria-hidden />
              Calories match macros ({formatNumber(computed)} kcal)
            </p>
          ))}

        <button
          type="button"
          aria-expanded={showMore}
          aria-controls="cf-more"
          onClick={() => setShowMore((open) => !open)}
          className="flex h-12 items-center gap-2 rounded-xl border bg-secondary px-4 text-left text-sm font-medium outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="flex-1">
            More nutrients <span className="font-normal text-muted-foreground">· fibre, sugar, sodium</span>
          </span>
          <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", showMore && "rotate-180")} aria-hidden />
        </button>
        {showMore && (
          <div id="cf-more" className="grid grid-cols-3 gap-3">
            <FormField id="cf-fibre" label="Fibre" suffix="g" inputMode="decimal" placeholder="—" error={errors.fibreG?.message} {...register("fibreG")} />
            <FormField id="cf-sugar" label="Sugar" suffix="g" inputMode="decimal" placeholder="—" error={errors.sugarG?.message} {...register("sugarG")} />
            <FormField id="cf-sodium" label="Sodium" suffix="mg" inputMode="decimal" placeholder="—" error={errors.sodiumMg?.message} {...register("sodiumMg")} />
          </div>
        )}
      </div>

      {/* Live preview — desktop only */}
      <aside aria-label="Preview" className="hidden flex-col gap-4 self-start rounded-2xl border bg-background p-5 lg:col-span-5 lg:flex">
        <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Preview</p>
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl bg-secondary text-muted-foreground">
            <UtensilsCrossed className="size-5" aria-hidden />
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-semibold">{name}</span>
            <span className="text-xs text-muted-foreground">
              Custom · {servingSize ? `${formatNumber(servingSize, 2)} ${servingUnit}` : "—"}
              {weight && servingUnit !== "g" ? ` (${formatNumber(weight)} g)` : ""}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-5">
          <CalorieRing value={calories} max={targets.calories} size={104}>
            <span className="font-display text-2xl leading-none font-semibold">{formatNumber(calories)}</span>
            <span className="mt-0.5 text-[11px] text-muted-foreground">kcal</span>
          </CalorieRing>
          <div className="flex flex-1 flex-col gap-3">
            <MacroBar macro="protein" value={macros.protein} target={targets.protein} />
            <MacroBar macro="carbs" value={macros.carbs} target={targets.carbs} />
            <MacroBar macro="fat" value={macros.fat} target={targets.fat} />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">Share of your daily targets</p>

        <div className="flex flex-col gap-2 border-t pt-4">
          <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Energy split</p>
          <div className="flex h-2.5 overflow-hidden rounded-full bg-border">
            <div className="bg-protein" style={{ width: `${split.protein}%` }} />
            <div className="bg-carbs" style={{ width: `${split.carbs}%` }} />
            <div className="bg-fat" style={{ width: `${split.fat}%` }} />
          </div>
          <p className="flex gap-4 text-xs text-muted-foreground">
            <span>Protein {split.protein}%</span>
            <span>Carbs {split.carbs}%</span>
            <span>Fat {split.fat}%</span>
          </p>
        </div>

        {per100 && (
          <div className="flex flex-col gap-2 border-t pt-4">
            <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Per 100 g</p>
            <dl className="grid grid-cols-4 gap-2">
              {[
                ["kcal", formatNumber(calories * per100)],
                ["Protein", `${formatNumber(macros.protein * per100, 1)}g`],
                ["Carbs", `${formatNumber(macros.carbs * per100, 1)}g`],
                ["Fat", `${formatNumber(macros.fat * per100, 1)}g`],
              ].map(([label, value]) => (
                <div key={label}>
                  <dd className="font-display text-xl font-semibold">{value}</dd>
                  <dt className="text-[11px] text-muted-foreground">{label}</dt>
                </div>
              ))}
            </dl>
          </div>
        )}
      </aside>

      <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-end lg:col-span-12">
        <p className="mr-auto hidden text-[13px] text-muted-foreground sm:block">Saved foods appear in search as “My food”.</p>
        <Button type="button" variant="outline" className="h-12 rounded-xl px-5" onClick={saveOnly}>
          Save only
        </Button>
        <Button type="submit" className="h-12 rounded-xl px-5 text-[15px] font-semibold">
          <Check /> Save &amp; log to {MEAL_LABELS[logMeal]}
        </Button>
      </div>
    </form>
  )
}
