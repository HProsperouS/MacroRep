import { zodResolver } from "@hookform/resolvers/zod"
import { ArrowLeft } from "lucide-react"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { EQUIPMENT, EQUIPMENT_LABELS, MUSCLE_GROUPS, MUSCLE_LABELS, type CreateExerciseInput } from "@/types/workout"

const createExerciseSchema = z.object({
  name: z.string().trim().min(2, "Enter a name").max(60, "Keep it under 60 characters"),
  equipment: z.enum(EQUIPMENT, { errorMap: () => ({ message: "Choose the equipment" }) }),
  muscles: z.array(z.enum(MUSCLE_GROUPS)).min(1, "Choose at least one muscle group").max(4, "Choose up to 4"),
})

type CreateExerciseValues = z.infer<typeof createExerciseSchema>

type CreateExerciseFormProps = {
  defaultName: string
  submitting: boolean
  onBack: () => void
  onSubmit: (input: CreateExerciseInput) => void
}

export function CreateExerciseForm({ defaultName, submitting, onBack, onSubmit }: CreateExerciseFormProps) {
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CreateExerciseValues>({
    resolver: zodResolver(createExerciseSchema),
    // equipment starts unset so the user makes a deliberate choice.
    defaultValues: { name: defaultName, equipment: undefined, muscles: [] },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <TextField id="exercise-name" label="Name" autoFocus placeholder="e.g. Chest-supported row" error={errors.name?.message} disabled={submitting} {...register("name")} />

        <Controller
          control={control}
          name="equipment"
          render={({ field }) => (
            <Field data-invalid={errors.equipment ? true : undefined}>
              <FieldLabel htmlFor="exercise-equipment">Equipment</FieldLabel>
              <Select value={field.value ?? ""} onValueChange={field.onChange} disabled={submitting}>
                <SelectTrigger id="exercise-equipment" className="w-full data-[size=default]:h-10" aria-invalid={errors.equipment ? true : undefined}>
                  <SelectValue placeholder="Choose equipment" />
                </SelectTrigger>
                <SelectContent>
                  {EQUIPMENT.map((equipment) => (
                    <SelectItem key={equipment} value={equipment}>
                      {EQUIPMENT_LABELS[equipment]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.equipment ? <FieldError>{errors.equipment.message}</FieldError> : null}
            </Field>
          )}
        />

        <Controller
          control={control}
          name="muscles"
          render={({ field }) => (
            <FieldSet className="gap-2" data-invalid={errors.muscles ? true : undefined}>
              <FieldLegend variant="label">Muscles worked</FieldLegend>
              <ToggleGroup
                type="multiple"
                variant="outline"
                size="sm"
                value={field.value}
                onValueChange={field.onChange}
                aria-label="Muscles worked"
                className="flex-wrap"
                disabled={submitting}
              >
                {MUSCLE_GROUPS.map((muscle) => (
                  <ToggleGroupItem key={muscle} value={muscle} className="h-9 px-3">
                    {MUSCLE_LABELS[muscle]}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
              {errors.muscles ? <FieldError>{errors.muscles.message}</FieldError> : <FieldDescription>Main muscles first. Used for search filters.</FieldDescription>}
            </FieldSet>
          )}
        />
      </FieldGroup>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <Button type="button" variant="ghost" className="h-10" onClick={onBack} disabled={submitting}>
          <ArrowLeft data-icon="inline-start" />
          Back to search
        </Button>
        <Button type="submit" className="h-10" disabled={submitting}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Create and add
        </Button>
      </div>
    </form>
  )
}
