import { zodResolver } from "@hookform/resolvers/zod"
import { TriangleAlert } from "lucide-react"
import { Controller, useForm, useWatch, type Control, type UseFormRegisterReturn } from "react-hook-form"
import { z } from "zod"

import { ActivityChoice, ExperienceChoice, GoalChoice, SexChoice } from "@/components/profile/profile-choices"
import { TextField } from "@/components/ui/text-field"
import { Button } from "@/components/ui/button"
import { FieldDescription, FieldError, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { toDayKey } from "@/lib/dates"
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
    setValue,
    clearErrors,
    formState: { errors, isDirty },
  } = useForm<ProfileInput, unknown, ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: profile.name,
      heightCm: String(profile.heightCm),
      goal: profile.goal,
      weeklyRate: String(Math.abs(profile.weeklyRateKg)),
      experienceLevel: profile.experienceLevel,
      dateOfBirth: profile.dateOfBirth ?? "",
      sex: profile.sex ?? undefined,
      activityLevel: profile.activityLevel ?? undefined,
    },
  })

  const submit = handleSubmit((values) => onSubmit(toUpdateProfileInput(values)))

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="profile-name" label="Name" autoComplete="name" error={errors.name?.message} disabled={submitting} {...register("name")} />
          <TextField id="profile-email" label="Email" value={profile.email} readOnly disabled description="Used to sign in" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <TextField id="profile-birth" label="Date of birth" type="date" max={toDayKey(new Date())} error={errors.dateOfBirth?.message} disabled={submitting} {...register("dateOfBirth")} />
          <FieldSet className="gap-2">
            <FieldLegend variant="label">Sex</FieldLegend>
            <Controller control={control} name="sex" render={({ field }) => <SexChoice value={field.value} onChange={field.onChange} disabled={submitting} />} />
            <FieldError errors={[errors.sex]} />
          </FieldSet>
        </div>

        <FieldSet className="gap-2">
          <FieldLegend variant="label">Goal</FieldLegend>
          <Controller
            control={control}
            name="goal"
            render={({ field }) => (
              <GoalChoice
                value={field.value}
                onChange={(value) => {
                  field.onChange(value)
                  // Maintaining hides the rate: one typed in for another goal mustn't block
                  // saving with an error the user can't see.
                  if (value === "maintain") {
                    setValue("weeklyRate", "0.5")
                    clearErrors("weeklyRate")
                  }
                }}
                disabled={submitting}
              />
            )}
          />
          <FieldDescription>Your coach adjusts your calorie target towards it.</FieldDescription>
        </FieldSet>

        <div className="grid gap-4 sm:grid-cols-2">
          <RateField control={control} error={errors.weeklyRate?.message} disabled={submitting} register={register("weeklyRate")} />
          <TextField id="profile-height" label="Height" unit="cm" inputMode="decimal" error={errors.heightCm?.message} disabled={submitting} {...register("heightCm")} />
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
          <FieldLegend variant="label">Daily activity, training included</FieldLegend>
          <Controller
            control={control}
            name="activityLevel"
            render={({ field }) => <ActivityChoice id="profile-activity" value={field.value} onChange={field.onChange} disabled={submitting} />}
          />
          <FieldError errors={[errors.activityLevel]} />
          <FieldDescription>Used with your age, sex, height and weight to estimate your targets.</FieldDescription>
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

/** The weekly rate for a goal, with a caution beyond the usual rates. Maintaining has none to ask. */
export function RateInput({ goal, rateRaw, error, disabled, register }: RateInputProps) {
  if (goal === "maintain") return null
  const rate = toNumber(rateRaw)
  const usualMax = goal === undefined ? undefined : USUAL_MAX_RATE_KG[goal]
  const aboveUsual = usualMax !== undefined && rate !== undefined && rate > usualMax && !error

  return (
    <div className="flex flex-col gap-2">
      <TextField
        id="profile-rate"
        label={goal === "gain" ? "Gain per week" : "Loss per week"}
        unit="kg"
        inputMode="decimal"
        description="0.25–0.5 kg is sustainable for most people"
        error={error}
        disabled={disabled}
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
