import { zodResolver } from "@hookform/resolvers/zod"
import { format } from "date-fns"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { toNumber } from "@/lib/format"

const weighInSchema = z.object({
  weightKg: z.preprocess(
    (value) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN),
    z.number({ required_error: "Enter your weight", invalid_type_error: "Enter a number" }).min(25, "That looks too low").max(400, "That looks too high"),
  ),
})

type WeighInInput = z.input<typeof weighInSchema>
type WeighInValues = z.output<typeof weighInSchema>

type WeighInFormProps = {
  lastWeightKg?: number
  submitting: boolean
  onCancel: () => void
  onSubmit: (weightKg: number) => void
}

export function WeighInForm({ lastWeightKg, submitting, onCancel, onSubmit }: WeighInFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<WeighInInput, unknown, WeighInValues>({
    resolver: zodResolver(weighInSchema),
    defaultValues: { weightKg: "" },
  })

  return (
    <form onSubmit={handleSubmit((values) => onSubmit(values.weightKg))} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <TextField
          id="weigh-in-weight"
          label={`Weight · ${format(new Date(), "EEE d MMM")}`}
          unit="kg"
          inputMode="decimal"
          autoFocus
          placeholder={lastWeightKg ? String(lastWeightKg) : "72.0"}
          description="Weigh in the morning, after the bathroom and before eating."
          error={errors.weightKg?.message}
          disabled={submitting}
          {...register("weightKg")}
        />
      </FieldGroup>
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" className="h-10" disabled={submitting}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Save weigh-in
        </Button>
      </div>
    </form>
  )
}
