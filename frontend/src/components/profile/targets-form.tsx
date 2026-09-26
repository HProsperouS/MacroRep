import { zodResolver } from "@hookform/resolvers/zod"
import { Check, TriangleAlert } from "lucide-react"
import { useForm, useWatch, type Control } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesFromMacros, caloriesImplausiblyLow, caloriesMismatch, implausibleCaloriesMessage } from "@/lib/macros"
import { requiredNumber } from "@/lib/zod-helpers"
import type { DailyTargets } from "@/types/food"

const targetsSchema = z
  .object({
    calories: requiredNumber("calories", 1000, 6000),
    protein: requiredNumber("protein", 0, 500),
    carbs: requiredNumber("carbs", 0, 1000),
    fat: requiredNumber("fat", 0, 400),
  })
  .superRefine((v, ctx) => {
    if (caloriesImplausiblyLow(v.calories, v)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: implausibleCaloriesMessage(v), path: ["calories"] })
    }
  })

type TargetsInput = z.input<typeof targetsSchema>
type TargetsValues = z.output<typeof targetsSchema>

type TargetsFormProps = {
  targets: DailyTargets
  submitting: boolean
  onSubmit: (targets: DailyTargets) => void
}

export function TargetsForm({ targets, submitting, onSubmit }: TargetsFormProps) {
  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<TargetsInput, unknown, TargetsValues>({
    resolver: zodResolver(targetsSchema),
    defaultValues: {
      calories: String(targets.calories),
      protein: String(targets.protein),
      carbs: String(targets.carbs),
      fat: String(targets.fat),
    },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <TextField
          id="targets-calories"
          label="Calories"
          unit="kcal"
          inputMode="numeric"
          dotClassName="bg-calories"
          error={errors.calories?.message}
          disabled={submitting}
          {...register("calories")}
        />
        <div className="grid grid-cols-3 gap-3">
          <TextField id="targets-protein" label="Protein" unit="g" inputMode="numeric" dotClassName="bg-protein" error={errors.protein?.message} disabled={submitting} {...register("protein")} />
          <TextField id="targets-carbs" label="Carbs" unit="g" inputMode="numeric" dotClassName="bg-carbs" error={errors.carbs?.message} disabled={submitting} {...register("carbs")} />
          <TextField id="targets-fat" label="Fat" unit="g" inputMode="numeric" dotClassName="bg-fat" error={errors.fat?.message} disabled={submitting} {...register("fat")} />
        </div>
        <MacroCheck control={control} />
      </FieldGroup>
      <div className="flex justify-end">
        <Button type="submit" className="h-10 w-full sm:w-auto" disabled={submitting || !isDirty}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Save targets
        </Button>
      </div>
    </form>
  )
}

function MacroCheck({ control }: { control: Control<TargetsInput, unknown, TargetsValues> }) {
  const [caloriesRaw, proteinRaw, carbsRaw, fatRaw] = useWatch({ control, name: ["calories", "protein", "carbs", "fat"] })
  const macros = { protein: toNumber(proteinRaw) ?? 0, carbs: toNumber(carbsRaw) ?? 0, fat: toNumber(fatRaw) ?? 0 }
  const computed = caloriesFromMacros(macros)
  const calories = toNumber(caloriesRaw)
  if (computed === 0 || calories === undefined) return null

  return caloriesMismatch(calories, macros) ? (
    <p className="flex items-center gap-2 text-sm text-carbs" role="status">
      <TriangleAlert className="size-4 shrink-0" aria-hidden />
      Macros add up to {formatNumber(computed)} kcal, which doesn’t match {formatNumber(calories)} kcal.
    </p>
  ) : (
    <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
      <Check className="size-4 shrink-0 text-primary" aria-hidden />
      Macros add up to {formatNumber(computed)} kcal
    </p>
  )
}
