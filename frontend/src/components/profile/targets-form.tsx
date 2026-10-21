import { zodResolver } from "@hookform/resolvers/zod"
import { Check, TriangleAlert } from "lucide-react"
import { useForm, useWatch, type Control, type UseFormRegisterReturn } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/ui/text-field"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { formatNumber, toNumber } from "@/lib/format"
import { caloriesFromMacros, caloriesMismatch } from "@/lib/macros"
import { checkTargetCalories, targetsFields } from "@/lib/profile-schemas"
import type { DailyTargets } from "@/types/food"

const targetsSchema = targetsFields.superRefine(checkTargetCalories)

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
        <TargetsFields
          idPrefix="targets"
          fields={{ calories: register("calories"), protein: register("protein"), carbs: register("carbs"), fat: register("fat") }}
          errors={{ calories: errors.calories?.message, protein: errors.protein?.message, carbs: errors.carbs?.message, fat: errors.fat?.message }}
          disabled={submitting}
        />
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

type TargetField = "calories" | "protein" | "carbs" | "fat"

type TargetsFieldsProps = {
  idPrefix: string
  fields: Record<TargetField, UseFormRegisterReturn>
  errors: Partial<Record<TargetField, string>>
  disabled: boolean
}

/** The four daily targets' inputs, for this form and the sign-up guide. */
export function TargetsFields({ idPrefix, fields, errors, disabled }: TargetsFieldsProps) {
  return (
    <>
      <TextField id={`${idPrefix}-calories`} label="Calories" unit="kcal" inputMode="numeric" dotClassName="bg-calories" error={errors.calories} disabled={disabled} {...fields.calories} />
      <div className="grid grid-cols-3 gap-3">
        <TextField id={`${idPrefix}-protein`} label="Protein" unit="g" inputMode="numeric" dotClassName="bg-protein" error={errors.protein} disabled={disabled} {...fields.protein} />
        <TextField id={`${idPrefix}-carbs`} label="Carbs" unit="g" inputMode="numeric" dotClassName="bg-carbs" error={errors.carbs} disabled={disabled} {...fields.carbs} />
        <TextField id={`${idPrefix}-fat`} label="Fat" unit="g" inputMode="numeric" dotClassName="bg-fat" error={errors.fat} disabled={disabled} {...fields.fat} />
      </div>
    </>
  )
}

function MacroCheck({ control }: { control: Control<TargetsInput, unknown, TargetsValues> }) {
  const [calories, protein, carbs, fat] = useWatch({ control, name: ["calories", "protein", "carbs", "fat"] })
  return <MacroSummary calories={calories} protein={protein} carbs={carbs} fat={fat} />
}

/** Whether the macros, as typed, add up to the calories. */
export function MacroSummary({ calories: caloriesRaw, protein: proteinRaw, carbs: carbsRaw, fat: fatRaw }: Record<"calories" | "protein" | "carbs" | "fat", unknown>) {
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
