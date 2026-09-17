import { zodResolver } from "@hookform/resolvers/zod"
import { Check, ChevronDown, TriangleAlert, UtensilsCrossed } from "lucide-react"
import { useState } from "react"
import { Controller, useForm, useWatch, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form"
import { z } from "zod"

import { CalorieRing } from "@/components/charts/calorie-ring"
import { MacroBar } from "@/components/charts/macro-bar"
import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import type { QuickAddDraft } from "@/components/food/quick-add-form"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesFromMacros, caloriesMismatch, energySplit } from "@/lib/macros"
import { MEAL_LABELS, MEAL_TYPES, SERVING_UNITS, type DailyTargets, type Food, type MealType } from "@/types/food"

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
type CustomFoodControl = Control<CustomFoodInput, unknown, CustomFoodValues>

export type CustomFoodSubmit = {
  food: Omit<Food, "id" | "source">
  logTo: MealType | null
}

type CustomFoodFormProps = {
  defaultMeal: MealType
  draft?: QuickAddDraft
  targets: DailyTargets
  /** Resolve when saved; reject to keep the form open. */
  onSubmit: (result: CustomFoodSubmit) => Promise<void>
}

const toInput = (value: number | undefined) => (value === undefined ? "" : String(value))

export function CustomFoodForm({ defaultMeal, draft, targets, onSubmit }: CustomFoodFormProps) {
  const [showMore, setShowMore] = useState(false)
  const [submitMode, setSubmitMode] = useState<"save" | "log">("log")
  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CustomFoodInput, unknown, CustomFoodValues>({
    resolver: zodResolver(customFoodSchema),
    defaultValues: {
      name: draft?.name ?? "",
      brand: "",
      servingSize: "1",
      servingUnit: "piece",
      servingWeightG: "",
      calories: toInput(draft?.calories),
      protein: toInput(draft?.protein),
      carbs: toInput(draft?.carbs),
      fat: toInput(draft?.fat),
      fibreG: "",
      sugarG: "",
      sodiumMg: "",
      meal: defaultMeal,
    },
  })

  const submitWith = (mode: "save" | "log") =>
    handleSubmit(async (values) => {
      setSubmitMode(mode)
      await onSubmit({
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
        logTo: mode === "log" ? values.meal : null,
      })
    })

  return (
    <form onSubmit={submitWith("log")} noValidate className="grid gap-6 lg:grid-cols-12">
      <FieldGroup className="lg:col-span-7">
        <TextField id="cf-name" label="Food name" placeholder="e.g. Mum’s fried rice" error={errors.name?.message} {...register("name")} />

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="cf-brand" label="Brand or place" description="Optional" placeholder="e.g. Koufu" error={errors.brand?.message} {...register("brand")} />
          <Field>
            <FieldLabel htmlFor="cf-meal">Log to</FieldLabel>
            <Controller
              control={control}
              name="meal"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="cf-meal" className="h-10 w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {MEAL_TYPES.map((meal) => (
                        <SelectItem key={meal} value={meal}>
                          {MEAL_LABELS[meal]}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
        </div>

        <FieldSet>
          <FieldLegend variant="label">Serving</FieldLegend>
          <ServingFields control={control} register={register} errors={errors} />
        </FieldSet>

        <Separator />

        <FieldSet>
          <FieldLegend variant="label">Nutrition per serving</FieldLegend>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <TextField id="cf-calories" label="Calories" unit="kcal" inputMode="decimal" placeholder="0" dotClassName="bg-calories" error={errors.calories?.message} {...register("calories")} />
            <TextField id="cf-protein" label="Protein" unit="g" inputMode="decimal" placeholder="0" dotClassName="bg-protein" error={errors.protein?.message} {...register("protein")} />
            <TextField id="cf-carbs" label="Carbs" unit="g" inputMode="decimal" placeholder="0" dotClassName="bg-carbs" error={errors.carbs?.message} {...register("carbs")} />
            <TextField id="cf-fat" label="Fat" unit="g" inputMode="decimal" placeholder="0" dotClassName="bg-fat" error={errors.fat?.message} {...register("fat")} />
          </div>
          <MacroConsistency control={control} />
        </FieldSet>

        <Button type="button" variant="outline" className="h-10 justify-between" aria-expanded={showMore} aria-controls="cf-more" onClick={() => setShowMore((open) => !open)}>
          <span>
            More nutrients <span className="font-normal text-muted-foreground">· fibre, sugar, sodium</span>
          </span>
          <ChevronDown data-icon="inline-end" className={showMore ? "rotate-180" : undefined} />
        </Button>
        {showMore ? (
          <div id="cf-more" className="grid grid-cols-3 gap-3">
            <TextField id="cf-fibre" label="Fibre" unit="g" inputMode="decimal" placeholder="—" error={errors.fibreG?.message} {...register("fibreG")} />
            <TextField id="cf-sugar" label="Sugar" unit="g" inputMode="decimal" placeholder="—" error={errors.sugarG?.message} {...register("sugarG")} />
            <TextField id="cf-sodium" label="Sodium" unit="mg" inputMode="decimal" placeholder="—" error={errors.sodiumMg?.message} {...register("sodiumMg")} />
          </div>
        ) : null}
      </FieldGroup>

      <CustomFoodPreview control={control} targets={targets} />

      <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-end lg:col-span-12">
        <p className="mr-auto hidden text-sm text-muted-foreground sm:block">Saved foods appear in search as “My food”.</p>
        <Button type="button" variant="outline" size="lg" className="h-11" disabled={isSubmitting} onClick={submitWith("save")}>
          {isSubmitting && submitMode === "save" ? <Spinner data-icon="inline-start" /> : null}
          Save only
        </Button>
        <SaveAndLogButton control={control} pending={isSubmitting && submitMode === "log"} disabled={isSubmitting} />
      </div>
    </form>
  )
}

type ServingFieldsProps = {
  control: CustomFoodControl
  register: UseFormRegister<CustomFoodInput>
  errors: FieldErrors<CustomFoodInput>
}

function ServingFields({ control, register, errors }: ServingFieldsProps) {
  const unit = useWatch({ control, name: "servingUnit" })
  return (
    <div className="grid grid-cols-3 items-start gap-3">
      <TextField id="cf-serving" label="Size" inputMode="decimal" error={errors.servingSize?.message} {...register("servingSize")} />
      <Field>
        <FieldLabel htmlFor="cf-unit">Unit</FieldLabel>
        <Controller
          control={control}
          name="servingUnit"
          render={({ field }) => (
            <Select value={field.value} onValueChange={field.onChange}>
              <SelectTrigger id="cf-unit" className="h-10 w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {SERVING_UNITS.map((servingUnit) => (
                    <SelectItem key={servingUnit} value={servingUnit}>
                      {servingUnit}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          )}
        />
      </Field>
      <TextField
        id="cf-weight"
        label="Weight"
        unit="g"
        inputMode="decimal"
        placeholder="—"
        disabled={unit === "g"}
        description={unit === "g" ? "Same as size" : undefined}
        error={errors.servingWeightG?.message}
        {...register("servingWeightG")}
      />
    </div>
  )
}

function MacroConsistency({ control }: { control: CustomFoodControl }) {
  const [caloriesRaw, proteinRaw, carbsRaw, fatRaw] = useWatch({ control, name: ["calories", "protein", "carbs", "fat"] })
  const calories = toNumber(caloriesRaw) ?? 0
  const macros = { protein: toNumber(proteinRaw) ?? 0, carbs: toNumber(carbsRaw) ?? 0, fat: toNumber(fatRaw) ?? 0 }
  const computed = caloriesFromMacros(macros)

  if (calories === 0 || computed === 0) return null

  return caloriesMismatch(calories, macros) ? (
    <p role="status" className="flex items-start gap-2 text-sm text-muted-foreground">
      <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      Macros add up to {formatNumber(computed)} kcal — check the label for alcohol or fibre.
    </p>
  ) : (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Check aria-hidden className="size-4 text-primary" />
      Calories match macros ({formatNumber(computed)} kcal)
    </p>
  )
}

function SaveAndLogButton({ control, pending, disabled }: { control: CustomFoodControl; pending: boolean; disabled: boolean }) {
  const meal = useWatch({ control, name: "meal" })
  return (
    <Button type="submit" size="lg" className="h-11" disabled={disabled}>
      {pending ? <Spinner data-icon="inline-start" /> : <Check data-icon="inline-start" />}
      Save &amp; log to {MEAL_LABELS[meal]}
    </Button>
  )
}

/** Desktop-only live preview. Owns its own subscription so typing doesn't re-render the form. */
function CustomFoodPreview({ control, targets }: { control: CustomFoodControl; targets: DailyTargets }) {
  const [nameRaw, sizeRaw, unit, weightRaw, caloriesRaw, proteinRaw, carbsRaw, fatRaw] = useWatch({
    control,
    name: ["name", "servingSize", "servingUnit", "servingWeightG", "calories", "protein", "carbs", "fat"],
  })

  const name = nameRaw.trim() || "Untitled food"
  const size = toNumber(sizeRaw)
  const weight = unit === "g" ? size : toNumber(weightRaw)
  const calories = toNumber(caloriesRaw) ?? 0
  const macros = { protein: toNumber(proteinRaw) ?? 0, carbs: toNumber(carbsRaw) ?? 0, fat: toNumber(fatRaw) ?? 0 }
  const split = energySplit(macros)
  const per100 = weight !== undefined && weight > 0 ? 100 / weight : undefined

  return (
    <aside aria-label="Preview" className="hidden flex-col gap-4 self-start rounded-xl border p-4 lg:col-span-5 lg:flex">
      <p className="text-sm font-medium">Preview</p>
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <UtensilsCrossed aria-hidden className="size-5" />
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-medium">{name}</span>
          <span className="truncate text-xs text-muted-foreground">
            Custom · {size !== undefined ? `${formatNumber(size, 2)} ${unit}` : "—"}
            {unit !== "g" && weight !== undefined ? ` (${formatNumber(weight)} g)` : ""}
          </span>
        </span>
      </div>

      <div className="flex items-center gap-5">
        <CalorieRing value={calories} max={targets.calories} size={96}>
          <span className="font-display text-2xl leading-none font-semibold">{formatNumber(calories)}</span>
          <span className="mt-0.5 text-xs text-muted-foreground">kcal</span>
        </CalorieRing>
        <div className="flex flex-1 flex-col gap-3">
          <MacroBar macro="protein" value={macros.protein} target={targets.protein} />
          <MacroBar macro="carbs" value={macros.carbs} target={targets.carbs} />
          <MacroBar macro="fat" value={macros.fat} target={targets.fat} />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Bars show share of your daily targets.</p>

      <Separator />
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Energy split</p>
        <div className="flex h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
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

      {per100 !== undefined ? (
        <>
          <Separator />
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium">Per 100 g</p>
            <dl className="grid grid-cols-4 gap-2">
              <PreviewStat label="kcal" value={formatNumber(calories * per100)} />
              <PreviewStat label="Protein" value={`${formatNumber(macros.protein * per100, 1)}g`} />
              <PreviewStat label="Carbs" value={`${formatNumber(macros.carbs * per100, 1)}g`} />
              <PreviewStat label="Fat" value={`${formatNumber(macros.fat * per100, 1)}g`} />
            </dl>
          </div>
        </>
      ) : null}
    </aside>
  )
}

function PreviewStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col-reverse">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-display text-lg font-semibold">{value}</dd>
    </div>
  )
}
