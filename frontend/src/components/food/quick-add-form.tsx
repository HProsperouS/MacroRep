import { zodResolver } from "@hookform/resolvers/zod"
import { ArrowRight, Check, TriangleAlert, Zap } from "lucide-react"
import { useState } from "react"
import { Controller, useForm, useWatch, type Control, type UseFormSetValue } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { MealPicker } from "@/components/food/meal-picker"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesFromMacros, caloriesImplausiblyLow, caloriesMismatch, implausibleCaloriesMessage, type Nutrition } from "@/lib/macros"
import { MEAL_LABELS, MEAL_TYPES, type MealType } from "@/types/food"

const toNumberOrNaN = (value: unknown) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN)

const optionalAmount = (max: number) =>
  z.preprocess(
    toNumberOrNaN,
    z.number({ invalid_type_error: "Enter a number" }).min(0, "Can’t be negative").max(max, "That looks too high").optional(),
  )

const quickAddSchema = z
  .object({
    meal: z.enum(MEAL_TYPES),
    name: z.string().trim().max(60, "Keep it under 60 characters"),
    calories: optionalAmount(10_000),
    protein: optionalAmount(1_000),
    carbs: optionalAmount(1_000),
    fat: optionalAmount(1_000),
  })
  .refine((v) => (v.calories ?? 0) + (v.protein ?? 0) + (v.carbs ?? 0) + (v.fat ?? 0) > 0, {
    message: "Enter calories or at least one macro",
    path: ["calories"],
  })
  .superRefine((v, ctx) => {
    const macros = { protein: v.protein ?? 0, carbs: v.carbs ?? 0, fat: v.fat ?? 0 }
    // Blank calories are calculated from the macros, so only an entered value can be implausible.
    if (v.calories !== undefined && caloriesImplausiblyLow(v.calories, macros)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: implausibleCaloriesMessage(macros), path: ["calories"] })
    }
  })

type QuickAddInput = z.input<typeof quickAddSchema>
type QuickAddValues = z.output<typeof quickAddSchema>

export type QuickAddResult = Nutrition & { meal: MealType; name: string }
export type QuickAddDraft = Partial<Nutrition> & { name?: string }

type QuickAddFormProps = {
  defaultMeal: MealType
  onSubmit: (result: QuickAddResult) => void
  onSaveAsCustom: (draft: QuickAddDraft) => void
}

export function QuickAddForm({ defaultMeal, onSubmit, onSaveAsCustom }: QuickAddFormProps) {
  const {
    control,
    register,
    handleSubmit,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<QuickAddInput, unknown, QuickAddValues>({
    resolver: zodResolver(quickAddSchema),
    defaultValues: { meal: defaultMeal, name: "", calories: "", protein: "", carbs: "", fat: "" },
  })

  const submit = handleSubmit((values) => {
    const macros = { protein: values.protein ?? 0, carbs: values.carbs ?? 0, fat: values.fat ?? 0 }
    onSubmit({
      meal: values.meal,
      name: values.name || "Quick add",
      ...macros,
      calories: values.calories ?? caloriesFromMacros(macros),
    })
  })

  // Reads values only when clicked — no subscription needed.
  function saveAsCustom() {
    const values = getValues()
    const macros = { protein: toNumber(values.protein), carbs: toNumber(values.carbs), fat: toNumber(values.fat) }
    const computed = caloriesFromMacros({ protein: macros.protein ?? 0, carbs: macros.carbs ?? 0, fat: macros.fat ?? 0 })
    onSaveAsCustom({ name: values.name, ...macros, calories: toNumber(values.calories) ?? (computed || undefined) })
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <FieldSet className="gap-2">
          <FieldLegend variant="label">Meal</FieldLegend>
          <Controller control={control} name="meal" render={({ field }) => <MealPicker value={field.value} onChange={field.onChange} />} />
        </FieldSet>

        <TextField id="qa-name" label="Name" description="Optional — shown in your log" placeholder="e.g. Hawker lunch" error={errors.name?.message} {...register("name")} />

        <TextField
          id="qa-calories"
          label="Calories"
          unit="kcal"
          inputMode="decimal"
          placeholder="Calculated from macros if blank"
          dotClassName="bg-calories"
          error={errors.calories?.message}
          {...register("calories")}
        />

        <div className="grid grid-cols-3 gap-3">
          <TextField id="qa-protein" label="Protein" unit="g" inputMode="decimal" placeholder="0" dotClassName="bg-protein" error={errors.protein?.message} {...register("protein")} />
          <TextField id="qa-carbs" label="Carbs" unit="g" inputMode="decimal" placeholder="0" dotClassName="bg-carbs" error={errors.carbs?.message} {...register("carbs")} />
          <TextField id="qa-fat" label="Fat" unit="g" inputMode="decimal" placeholder="0" dotClassName="bg-fat" error={errors.fat?.message} {...register("fat")} />
        </div>

        <CalorieCheck control={control} setValue={setValue} />
      </FieldGroup>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Button type="button" variant="ghost" className="h-10" onClick={saveAsCustom}>
          Save as custom food instead
          <ArrowRight data-icon="inline-end" />
        </Button>
        <SubmitButton control={control} />
      </div>
    </form>
  )
}

/** Subscribes to the four numbers so the rest of the form doesn't re-render on each keystroke. */
function CalorieCheck({ control, setValue }: { control: Control<QuickAddInput, unknown, QuickAddValues>; setValue: UseFormSetValue<QuickAddInput> }) {
  const [caloriesRaw, proteinRaw, carbsRaw, fatRaw] = useWatch({ control, name: ["calories", "protein", "carbs", "fat"] })
  const [keptCalories, setKeptCalories] = useState<number>()

  const macros = { protein: toNumber(proteinRaw) ?? 0, carbs: toNumber(carbsRaw) ?? 0, fat: toNumber(fatRaw) ?? 0 }
  const computed = caloriesFromMacros(macros)
  const entered = toNumber(caloriesRaw)

  if (computed === 0) return null

  if (entered === undefined) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Zap aria-hidden className="size-4 text-primary" />
        Calories will be calculated: {formatNumber(computed)} kcal
      </p>
    )
  }

  // Derived: the warning hides only while the user keeps the exact value they confirmed.
  if (caloriesMismatch(entered, macros) && keptCalories !== entered) {
    return (
      <Alert>
        <TriangleAlert />
        <AlertTitle>Calories don’t match macros</AlertTitle>
        <AlertDescription>
          <p>
            Macros add up to {formatNumber(computed)} kcal, but you entered {formatNumber(entered)}. Alcohol or fibre can explain a gap.
          </p>
          <div className="flex flex-wrap gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setValue("calories", String(computed), { shouldValidate: true })}>
              Use {formatNumber(computed)} kcal
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setKeptCalories(entered)}>
              Keep {formatNumber(entered)}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Check aria-hidden className="size-4 text-primary" />
      Calories match macros ({formatNumber(computed)} kcal)
    </p>
  )
}

function SubmitButton({ control }: { control: Control<QuickAddInput, unknown, QuickAddValues> }) {
  const meal = useWatch({ control, name: "meal" })
  return (
    <Button type="submit" size="lg" className="h-11 sm:min-w-40">
      Add to {MEAL_LABELS[meal]}
    </Button>
  )
}
