import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { isLoggableDay, toDayKey } from "@/lib/dates"
import { toNumber } from "@/lib/format"
import type { WeighInInput } from "@/types/progress"

const weighInSchema = z.object({
  date: z.string().refine(isLoggableDay, "Pick today or an earlier day"),
  weightKg: z.preprocess(
    (value) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN),
    // Same 20–400 kg range the server accepts.
    z.number({ required_error: "Enter your weight", invalid_type_error: "Enter a number" }).min(20, "That looks too low").max(400, "That looks too high"),
  ),
})

type WeighInFormInput = z.input<typeof weighInSchema>
type WeighInFormValues = z.output<typeof weighInSchema>

type WeighInFormProps = {
  /** An existing weigh-in to edit; omit to add a new one for today. */
  initial?: WeighInInput
  lastWeightKg?: number
  submitting: boolean
  submitLabel?: string
  onCancel: () => void
  onSubmit: (values: WeighInInput) => void
}

export function WeighInForm({ initial, lastWeightKg, submitting, submitLabel = "Save weigh-in", onCancel, onSubmit }: WeighInFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<WeighInFormInput, unknown, WeighInFormValues>({
    resolver: zodResolver(weighInSchema),
    defaultValues: { date: initial?.date ?? toDayKey(new Date()), weightKg: initial ? String(initial.weightKg) : "" },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <TextField
          id="weigh-in-weight"
          label="Weight"
          unit="kg"
          inputMode="decimal"
          autoFocus
          placeholder={lastWeightKg ? String(lastWeightKg) : "72.0"}
          description="Weigh in the morning, after the bathroom and before eating."
          error={errors.weightKg?.message}
          disabled={submitting}
          {...register("weightKg")}
        />
        <TextField
          id="weigh-in-date"
          label="Day"
          type="date"
          max={toDayKey(new Date())}
          description={initial ? undefined : "Missed a day? Pick it here to fill it in."}
          error={errors.date?.message}
          disabled={submitting}
          {...register("date")}
        />
      </FieldGroup>
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" className="h-10" disabled={submitting}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
