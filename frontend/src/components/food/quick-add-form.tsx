import { zodResolver } from "@hookform/resolvers/zod"
import { Check, TriangleAlert, Zap } from "lucide-react"
import { useState } from "react"
import { Controller, useForm, useWatch } from "react-hook-form"
import { z } from "zod"

import { FormField } from "@/components/food/form-field"
import { MealPicker } from "@/components/food/meal-picker"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesFromMacros, caloriesMismatch, type Nutrition } from "@/lib/macros"
import { MEAL_LABELS, MEAL_TYPES, type MealType } from "@/types/food"

const optionalAmount = (max: number) =>
  z.preprocess(
    (value) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN),
    z
      .number({ invalid_type_error: "Enter a number" })
      .min(0, "Can’t be negative")
      .max(max, "That looks too high")
      .optional(),
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
  const [keepEntered, setKeepEntered] = useState(false)
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

  const [caloriesRaw, proteinRaw, carbsRaw, fatRaw, meal] = useWatch({
    control,
    name: ["calories", "protein", "carbs", "fat", "meal"],
  })
  const macros = { protein: toNumber(proteinRaw) ?? 0, carbs: toNumber(carbsRaw) ?? 0, fat: toNumber(fatRaw) ?? 0 }
  const computed = caloriesFromMacros(macros)
  const entered = toNumber(caloriesRaw)
  const hasMacros = computed > 0
  const mismatch = entered !== undefined && hasMacros && caloriesMismatch(entered, macros) && !keepEntered

  const submit = handleSubmit((values) => {
    const result: QuickAddResult = {
      meal: values.meal,
      name: values.name || "Quick add",
      protein: values.protein ?? 0,
      carbs: values.carbs ?? 0,
      fat: values.fat ?? 0,
      calories: values.calories ?? caloriesFromMacros({ protein: values.protein ?? 0, carbs: values.carbs ?? 0, fat: values.fat ?? 0 }),
    }
    onSubmit(result)
  })

  function switchToCustom() {
    const v = getValues()
    onSaveAsCustom({
      name: v.name,
      calories: toNumber(v.calories) ?? (hasMacros ? computed : undefined),
      protein: toNumber(v.protein),
      carbs: toNumber(v.carbs),
      fat: toNumber(v.fat),
    })
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <Controller control={control} name="meal" render={({ field }) => <MealPicker value={field.value} onChange={field.onChange} />} />

      <FormField id="qa-name" label="Name (optional)" placeholder="e.g. Hawker lunch" error={errors.name?.message} {...register("name")} />

      <FormField
        id="qa-calories"
        label="Calories"
        suffix="kcal"
        inputMode="decimal"
        placeholder={hasMacros ? String(computed) : "0"}
        dotClassName="bg-calories"
        inputClassName="h-14 font-display text-3xl font-semibold"
        hint={hasMacros ? undefined : "Leave blank to calculate from macros"}
        error={errors.calories?.message}
        {...register("calories", { onChange: () => setKeepEntered(false) })}
      />

      <div className="grid grid-cols-3 gap-2.5">
        <FormField id="qa-protein" label="Protein" suffix="g" inputMode="decimal" placeholder="0" dotClassName="bg-protein" error={errors.protein?.message} {...register("protein")} />
        <FormField id="qa-carbs" label="Carbs" suffix="g" inputMode="decimal" placeholder="0" dotClassName="bg-carbs" error={errors.carbs?.message} {...register("carbs")} />
        <FormField id="qa-fat" label="Fat" suffix="g" inputMode="decimal" placeholder="0" dotClassName="bg-fat" error={errors.fat?.message} {...register("fat")} />
      </div>

      {mismatch ? (
        <div role="status" className="flex gap-2.5 rounded-xl border border-carbs/35 bg-carbs/10 p-3 text-[13px] leading-relaxed">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-carbs" aria-hidden />
          <div className="flex flex-col gap-2">
            <p>
              Macros add up to <b>{formatNumber(computed)} kcal</b>, but you entered <b>{formatNumber(entered ?? 0)}</b>. Alcohol or
              fibre can explain a gap.
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" className="h-9" onClick={() => setValue("calories", String(computed), { shouldValidate: true })}>
                Use {formatNumber(computed)} kcal
              </Button>
              <Button type="button" variant="ghost" size="sm" className="h-9" onClick={() => setKeepEntered(true)}>
                Keep {formatNumber(entered ?? 0)}
              </Button>
            </div>
          </div>
        </div>
      ) : hasMacros ? (
        <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
          {entered === undefined ? <Zap className="size-4 text-primary" aria-hidden /> : <Check className="size-4 text-primary" aria-hidden />}
          {entered === undefined
            ? `Calories will be calculated: ${formatNumber(computed)} kcal`
            : `Calories match macros (${formatNumber(computed)} kcal)`}
        </p>
      ) : null}

      <label className="flex items-center gap-3 rounded-xl border bg-secondary px-4 py-3">
        <span className="flex flex-1 flex-col gap-0.5">
          <span className="text-sm font-medium">Save as custom food</span>
          <span className="text-xs text-muted-foreground">Add a serving size so you can reuse it</span>
        </span>
        <Switch checked={false} onCheckedChange={(checked) => checked && switchToCustom()} aria-label="Save as custom food" />
      </label>

      <Button type="submit" className="h-12 rounded-xl text-[15px] font-semibold">
        Add to {MEAL_LABELS[meal]}
      </Button>
    </form>
  )
}
