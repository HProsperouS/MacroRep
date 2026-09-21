import { zodResolver } from "@hookform/resolvers/zod"
import { Controller, useForm, useWatch, type Control, type UseFormRegisterReturn } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { FieldDescription, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { requiredNumber } from "@/lib/zod-helpers"
import { EXPERIENCE_LEVEL_LABELS, EXPERIENCE_LEVELS, GOAL_LABELS, GOALS, type Profile, type UpdateProfileInput } from "@/types/profile"
import { EQUIPMENT, EQUIPMENT_LABELS, type Equipment } from "@/types/workout"

const profileSchema = z.object({
  name: z.string().trim().min(1, "Enter your name").max(60, "Keep it under 60 characters"),
  heightCm: requiredNumber("your height", 100, 250),
  goal: z.enum(GOALS),
  weeklyRate: requiredNumber("a weekly rate", 0, 1),
  trainingDaysPerWeek: z.preprocess(
    (value) => Number(value),
    z.number().int("Whole days only").min(1, "At least 1 day").max(7, "At most 7 days"),
  ),
  experienceLevel: z.enum(EXPERIENCE_LEVELS),
  equipment: z.array(z.enum(EQUIPMENT)),
})

type ProfileInput = z.input<typeof profileSchema>
type ProfileValues = z.output<typeof profileSchema>

type ProfileFormProps = {
  profile: Profile
  submitting: boolean
  onSubmit: (input: UpdateProfileInput) => void
}

export function ProfileForm({ profile, submitting, onSubmit }: ProfileFormProps) {
  const {
    control,
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<ProfileInput, unknown, ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: profile.name,
      heightCm: String(profile.heightCm),
      goal: profile.goal,
      weeklyRate: String(Math.abs(profile.weeklyRateKg)),
      trainingDaysPerWeek: String(profile.trainingDaysPerWeek),
      experienceLevel: profile.experienceLevel,
      equipment: profile.equipment,
    },
  })

  const submit = handleSubmit((values) => {
    const rate = values.goal === "maintain" ? 0 : values.goal === "lose" ? -values.weeklyRate : values.weeklyRate
    onSubmit({
      name: values.name,
      heightCm: values.heightCm,
      goal: values.goal,
      weeklyRateKg: rate,
      trainingDaysPerWeek: values.trainingDaysPerWeek,
      experienceLevel: values.experienceLevel,
      equipment: values.equipment,
    })
  })

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="profile-name" label="Name" autoComplete="name" error={errors.name?.message} disabled={submitting} {...register("name")} />
          <TextField id="profile-email" label="Email" value={profile.email} readOnly disabled description="Managed by your sign-in provider" />
        </div>

        <FieldSet className="gap-2">
          <FieldLegend variant="label">Goal</FieldLegend>
          <Controller
            control={control}
            name="goal"
            render={({ field }) => (
              <ToggleGroup
                type="single"
                variant="outline"
                spacing={0}
                value={field.value}
                onValueChange={(next) => (next ? field.onChange(next) : undefined)}
                aria-label="Goal"
                className="w-full"
                disabled={submitting}
              >
                {GOALS.map((goal) => (
                  <ToggleGroupItem key={goal} value={goal} className="h-10 flex-1">
                    {GOAL_LABELS[goal]}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
          <FieldDescription>Your coach uses this to set calorie targets and training volume.</FieldDescription>
        </FieldSet>

        <div className="grid gap-4 sm:grid-cols-3">
          <RateField control={control} error={errors.weeklyRate?.message} disabled={submitting} register={register("weeklyRate")} />
          <TextField id="profile-height" label="Height" unit="cm" inputMode="decimal" error={errors.heightCm?.message} disabled={submitting} {...register("heightCm")} />
          <TextField
            id="profile-days"
            label="Training days"
            unit="/ week"
            inputMode="numeric"
            error={errors.trainingDaysPerWeek?.message}
            disabled={submitting}
            {...register("trainingDaysPerWeek")}
          />
        </div>

        <FieldSet className="gap-2">
          <FieldLegend variant="label">Training experience</FieldLegend>
          <Controller
            control={control}
            name="experienceLevel"
            render={({ field }) => (
              <ToggleGroup
                type="single"
                variant="outline"
                spacing={0}
                value={field.value}
                onValueChange={(next) => (next ? field.onChange(next) : undefined)}
                aria-label="Training experience"
                className="w-full"
                disabled={submitting}
              >
                {EXPERIENCE_LEVELS.map((level) => (
                  <ToggleGroupItem key={level} value={level} className="h-10 flex-1">
                    {EXPERIENCE_LEVEL_LABELS[level]}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
        </FieldSet>

        <FieldSet className="gap-2">
          <FieldLegend variant="label">Equipment you have access to</FieldLegend>
          <Controller
            control={control}
            name="equipment"
            render={({ field }) => (
              <ToggleGroup
                type="multiple"
                variant="outline"
                value={field.value}
                onValueChange={(next: Equipment[]) => field.onChange(next)}
                aria-label="Available equipment"
                className="flex-wrap"
                disabled={submitting}
              >
                {EQUIPMENT.map((item) => (
                  <ToggleGroupItem
                    key={item}
                    value={item}
                    className="h-10 data-[state=on]:border-primary/45 data-[state=on]:bg-primary/7"
                  >
                    {EQUIPMENT_LABELS[item]}
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            )}
          />
          <FieldDescription>Used to steer which exercises your coach proposes.</FieldDescription>
        </FieldSet>
      </FieldGroup>

      <div className="flex justify-end">
        <Button type="submit" className="h-10 w-full sm:w-auto" disabled={submitting || !isDirty}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Save profile
        </Button>
      </div>
    </form>
  )
}

type RateFieldProps = {
  control: Control<ProfileInput, unknown, ProfileValues>
  error?: string
  disabled: boolean
  register: UseFormRegisterReturn<"weeklyRate">
}

/** Watches the goal only here, so switching goals doesn't re-render the whole form. */
function RateField({ control, error, disabled, register }: RateFieldProps) {
  const goal = useWatch({ control, name: "goal" })
  const maintain = goal === "maintain"
  return (
    <TextField
      id="profile-rate"
      label={goal === "gain" ? "Gain per week" : "Loss per week"}
      unit="kg"
      inputMode="decimal"
      description={maintain ? "Not used when maintaining" : "0.25–0.5 kg is sustainable for most people"}
      error={maintain ? undefined : error}
      disabled={disabled || maintain}
      {...register}
    />
  )
}
