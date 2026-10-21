import { zodResolver } from "@hookform/resolvers/zod"
import { TriangleAlert } from "lucide-react"
import { Controller, useForm, useWatch, type Control, type UseFormRegisterReturn } from "react-hook-form"
import { z } from "zod"

import { EquipmentChoice, ExperienceChoice, GoalChoice } from "@/components/profile/profile-choices"
import { TextField } from "@/components/ui/text-field"
import { Button } from "@/components/ui/button"
import { FieldDescription, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { toNumber } from "@/lib/format"
import { profileSchema, toUpdateProfileInput } from "@/lib/profile-schemas"
import type { Goal, Profile, UpdateProfileInput } from "@/types/profile"

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

  const submit = handleSubmit((values) => onSubmit(toUpdateProfileInput(values)))

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
            render={({ field }) => <GoalChoice value={field.value} onChange={field.onChange} disabled={submitting} />}
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
            render={({ field }) => <ExperienceChoice value={field.value} onChange={field.onChange} disabled={submitting} />}
          />
        </FieldSet>

        <FieldSet className="gap-2">
          <FieldLegend variant="label">Equipment you have access to</FieldLegend>
          <Controller
            control={control}
            name="equipment"
            render={({ field }) => <EquipmentChoice value={field.value} onChange={field.onChange} disabled={submitting} />}
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

/**
 * Beyond these weekly rates, common guidance warns of muscle loss (losing) or mostly fat
 * gain (gaining). A caution, not a limit: the rate is the user's call.
 */
const USUAL_MAX_RATE_KG = { lose: 1, gain: 0.5 } as const

/** Watches the goal only here, so switching goals doesn't re-render the whole form. */
function RateField({ control, ...props }: RateFieldProps) {
  const [goal, rateRaw] = useWatch({ control, name: ["goal", "weeklyRate"] })
  return <RateInput goal={goal} rateRaw={rateRaw} {...props} />
}

type RateInputProps = Omit<RateFieldProps, "control"> & { goal: Goal | undefined; rateRaw: unknown }

/** The weekly rate for a goal, with a caution beyond the usual rates. */
export function RateInput({ goal, rateRaw, error, disabled, register }: RateInputProps) {
  const maintain = goal === "maintain"
  const rate = toNumber(rateRaw)
  const usualMax = maintain || goal === undefined ? undefined : USUAL_MAX_RATE_KG[goal]
  const aboveUsual = usualMax !== undefined && rate !== undefined && rate > usualMax && !error

  return (
    <div className="flex flex-col gap-2">
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
      {aboveUsual ? (
        <p className="flex items-start gap-2 text-sm text-carbs" role="status">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {goal === "lose"
            ? `Faster than the usual ${usualMax} kg a week. Losing this quickly tends to cost muscle and is hard to sustain.`
            : `Faster than the usual ${usualMax} kg a week. Gaining this quickly tends to add mostly fat.`}
        </p>
      ) : null}
    </div>
  )
}
