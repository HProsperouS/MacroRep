import { zodResolver } from "@hookform/resolvers/zod"
import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { Controller, useForm, useWatch, type Control, type FieldPath, type UseFormRegisterReturn } from "react-hook-form"
import { Navigate, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { z } from "zod"

import { apiErrorMessage, apiErrorStatus } from "@/api/client"
import { profileKeys } from "@/api/query-keys"
import { QueryError } from "@/components/layout/query-error"
import { ActivityChoice, ExperienceChoice, GoalChoice, SexChoice } from "@/components/profile/profile-choices"
import { RateInput } from "@/components/profile/profile-form"
import { MacroSummary, TargetsFields } from "@/components/profile/targets-form"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card"
import { FieldDescription, FieldError, FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field"
import { Progress } from "@/components/ui/progress"
import { Spinner } from "@/components/ui/spinner"
import { TextField } from "@/components/ui/text-field"
import { useNutritionTargets } from "@/hooks/use-food-log"
import { useCompleteOnboarding, useEstimateTargets, useProfile, useSyncTimezone } from "@/hooks/use-profile"
import { toDayKey } from "@/lib/dates"
import { formatNumber, toNumber } from "@/lib/format"
import { DEFAULT_WEEKLY_RATE, bodyWeightKg, checkTargetCalories, profileSchema, resetRateIfMaintaining, signedRate, targetsFields, toUpdateProfileInput } from "@/lib/profile-schemas"
import type { DailyTargets } from "@/types/food"
import { EXPERIENCE_LEVELS, GOALS, type EstimateTargetsInput, type Profile, type TargetEstimate } from "@/types/profile"

const onboardingSchema = profileSchema
  .extend({
    weightKg: bodyWeightKg,
    // Chosen, not defaulted: these steer the coach.
    goal: z.enum(GOALS, { required_error: "Choose a goal" }),
    experienceLevel: z.enum(EXPERIENCE_LEVELS, { required_error: "Choose your experience" }),
  })
  .merge(targetsFields)
  .superRefine(checkTargetCalories)

type OnboardingFormInput = z.input<typeof onboardingSchema>
type OnboardingValues = z.output<typeof onboardingSchema>

const STEPS: { title: string; description: string; fields: FieldPath<OnboardingFormInput>[] }[] = [
  {
    title: "About you",
    description: "These estimate your starting targets, and your weight starts the trend your coach follows.",
    fields: ["name", "dateOfBirth", "sex", "heightCm", "weightKg"],
  },
  { title: "Your goal", description: "Your coach sets calorie targets towards it.", fields: ["goal", "weeklyRate"] },
  {
    title: "Training",
    description: "Your coach paces training changes to your experience, and your activity helps estimate your targets.",
    fields: ["experienceLevel", "activityLevel"],
  },
  {
    title: "Daily targets",
    description: "Keep these or change them. Each weekly check-in then adjusts them from what you log.",
    fields: ["calories", "protein", "carbs", "fat"],
  },
]

const FINISH_AFTER_MS = 500

/** The sign-up guide (plan.md Journey 1): every step is filled in before the app opens. */
export default function OnboardingPage() {
  useSyncTimezone()
  const profile = useProfile()
  const targets = useNutritionTargets()

  if (profile.data?.onboarded) return <Navigate to="/" replace />
  return (
    <div className="flex min-h-dvh justify-center bg-background px-4 py-10">
      <div className="flex w-full max-w-lg flex-col gap-6">
        <span className="font-display text-2xl font-semibold tracking-wide text-foreground">MACROREP</span>
        {/* Once shown, the guide stays: a failed refetch mustn't throw away what was typed. */}
        {profile.data && !targets.isPending ? (
          // Without the starting targets the last step is simply left blank to fill in.
          <Guide profile={profile.data} targets={targets.data} />
        ) : profile.isError ? (
          <QueryError title="Couldn’t load your profile" error={profile.error} onRetry={() => void profile.refetch()} retrying={profile.isFetching} />
        ) : (
          <Spinner className="mx-auto size-6 text-muted-foreground" />
        )}
      </div>
    </div>
  )
}

function Guide({ profile, targets }: { profile: Profile; targets: DailyTargets | undefined }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const complete = useCompleteOnboarding()
  const estimateTargets = useEstimateTargets()
  const [step, setStep] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  const {
    control,
    register,
    trigger,
    setValue,
    getValues,
    clearErrors,
    handleSubmit,
    formState: { errors },
  } = useForm<OnboardingFormInput, unknown, OnboardingValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      name: profile.name,
      dateOfBirth: "",
      heightCm: "",
      weightKg: "",
      weeklyRate: DEFAULT_WEEKLY_RATE,
      calories: targets ? String(targets.calories) : "",
      protein: targets ? String(targets.protein) : "",
      carbs: targets ? String(targets.carbs) : "",
      fat: targets ? String(targets.fat) : "",
    },
  })
  const last = step === STEPS.length - 1
  const current = STEPS[step]
  const submitting = complete.isPending

  // Each step replaces the last in place, so move focus (and a screen reader) to its title.
  const moved = useRef(false)
  useEffect(() => {
    if (moved.current) heading.current?.focus()
    moved.current = true
  }, [step])

  // The same button reads Continue, then Finish setup: held back for a moment on the last
  // step, so a double click on the step before doesn't save targets the user hasn't seen.
  const [armed, setArmed] = useState(false)
  useEffect(() => {
    if (!last) return
    const timer = setTimeout(() => setArmed(true), FINISH_AFTER_MS)
    return () => {
      clearTimeout(timer)
      setArmed(false)
    }
  }, [last])

  const finish = handleSubmit((values) => {
    complete.mutate(
      {
        ...toUpdateProfileInput(values),
        weightKg: values.weightKg,
        targets: { calories: values.calories, protein: values.protein, carbs: values.carbs, fat: values.fat },
      },
      {
        onSuccess: () => {
          toast.success("You’re all set")
          navigate("/", { replace: true })
        },
        onError: async (error) => {
          // A 409 is either the guide already finished (e.g. in another tab), when the fresh
          // profile opens the app, or a clash with another change, which is worth saying.
          if (apiErrorStatus(error) === 409) {
            await queryClient.refetchQueries({ queryKey: profileKeys.all })
            if (queryClient.getQueryData<Profile>(profileKeys.all)?.onboarded) return
          }
          toast.error("Couldn’t finish setting up", { description: apiErrorMessage(error) })
        },
      },
    )
  })

  // The estimate behind the targets step, and the details it was made from: going back and
  // changing none of them keeps whatever the user then typed into the targets.
  const [estimate, setEstimate] = useState<TargetEstimate | null>(null)
  const estimatedFrom = useRef<string | null>(null)

  async function fillEstimate() {
    const values = getValues()
    const goal = values.goal as OnboardingValues["goal"]
    const input: EstimateTargetsInput = {
      heightCm: toNumber(values.heightCm) ?? 0,
      weightKg: toNumber(values.weightKg) ?? 0,
      dateOfBirth: values.dateOfBirth,
      sex: values.sex as OnboardingValues["sex"],
      activityLevel: values.activityLevel as OnboardingValues["activityLevel"],
      goal,
      weeklyRateKg: signedRate(goal, toNumber(values.weeklyRate) ?? 0),
    }
    const key = JSON.stringify(input)
    if (key === estimatedFrom.current) return
    try {
      const result = await estimateTargets.mutateAsync(input)
      for (const field of ["calories", "protein", "carbs", "fat"] as const) setValue(field, String(result[field]))
      setEstimate(result)
      estimatedFrom.current = key
    } catch {
      // Back to the general starting targets, as the step then says, and nothing remembered:
      // the next time through tries again.
      if (targets) for (const field of ["calories", "protein", "carbs", "fat"] as const) setValue(field, String(targets[field]))
      setEstimate(null)
      estimatedFrom.current = null
    }
  }

  async function next() {
    if (!(await trigger(current.fields))) return
    if (step + 1 === STEPS.length - 1) await fillEstimate()
    setStep(step + 1)
  }

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            Step {step + 1} of {STEPS.length}
          </p>
          <Progress value={((step + 1) / STEPS.length) * 100} aria-label="Setup progress" />
        </div>
        <h1 ref={heading} tabIndex={-1} className="text-lg font-semibold outline-none">
          {current.title}
        </h1>
        <CardDescription>{current.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          noValidate
          className="flex flex-col gap-6"
          onSubmit={(event) => {
            event.preventDefault()
            if (!last) void next()
            else if (armed) void finish()
          }}
        >
          <FieldGroup>
            {step === 0 ? (
              <>
                <TextField id="onboarding-name" label="Name" autoComplete="name" error={errors.name?.message} {...register("name")} />
                <div className="grid grid-cols-2 gap-4">
                  <TextField id="onboarding-birth" label="Date of birth" type="date" max={toDayKey(new Date())} error={errors.dateOfBirth?.message} {...register("dateOfBirth")} />
                  <Choice legend="Sex" error={errors.sex?.message}>
                    <Controller control={control} name="sex" render={({ field }) => <SexChoice value={field.value} onChange={field.onChange} />} />
                  </Choice>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <TextField id="onboarding-height" label="Height" unit="cm" inputMode="decimal" error={errors.heightCm?.message} {...register("heightCm")} />
                  <TextField id="onboarding-weight" label="Weight today" unit="kg" inputMode="decimal" error={errors.weightKg?.message} {...register("weightKg")} />
                </div>
              </>
            ) : null}

            {step === 1 ? (
              <>
                <Choice legend="Goal" error={errors.goal?.message}>
                  <Controller
                    control={control}
                    name="goal"
                    render={({ field }) => (
                      <GoalChoice
                        value={field.value}
                        onChange={(value) => {
                          field.onChange(value)
                          resetRateIfMaintaining(value, setValue, clearErrors)
                        }}
                      />
                    )}
                  />
                </Choice>
                <GuideRate control={control} error={errors.weeklyRate?.message} register={register("weeklyRate")} />
              </>
            ) : null}

            {step === 2 ? (
              <>
                <Choice legend="Training experience" error={errors.experienceLevel?.message}>
                  <Controller
                    control={control}
                    name="experienceLevel"
                    render={({ field }) => <ExperienceChoice value={field.value} onChange={field.onChange} />}
                  />
                </Choice>
                <Choice legend="Daily activity, training included" error={errors.activityLevel?.message}>
                  <Controller
                    control={control}
                    name="activityLevel"
                    render={({ field }) => <ActivityChoice id="onboarding-activity" value={field.value} onChange={field.onChange} />}
                  />
                </Choice>
              </>
            ) : null}

            {last ? (
              <>
                <TargetsFields
                  idPrefix="onboarding"
                  fields={{ calories: register("calories"), protein: register("protein"), carbs: register("carbs"), fat: register("fat") }}
                  errors={{ calories: errors.calories?.message, protein: errors.protein?.message, carbs: errors.carbs?.message, fat: errors.fat?.message }}
                  disabled={submitting}
                />
                <GuideMacros control={control} />
                <EstimateNote estimate={estimate} />
              </>
            ) : null}
          </FieldGroup>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
            {step > 0 ? (
              <Button type="button" variant="ghost" className="h-10" disabled={submitting} onClick={() => setStep(step - 1)}>
                Back
              </Button>
            ) : (
              <span />
            )}
            <Button type="submit" className="h-10" disabled={submitting || estimateTargets.isPending || (last && !armed)}>
              {submitting || estimateTargets.isPending ? <Spinner data-icon="inline-start" /> : null}
              {last ? "Finish setup" : "Continue"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

type GuideControl = Control<OnboardingFormInput, unknown, OnboardingValues>

/** Watches the goal and rate only here, so typing a rate doesn't re-render the whole guide. */
function GuideRate({ control, error, register }: { control: GuideControl; error?: string; register: UseFormRegisterReturn<"weeklyRate"> }) {
  const [goal, rateRaw] = useWatch({ control, name: ["goal", "weeklyRate"] })
  // Asked once a goal is chosen: the label and the caution depend on it.
  return goal ? <RateInput goal={goal} rateRaw={rateRaw} error={error} disabled={false} register={register} /> : null
}

/** Watches the targets only here, so typing one doesn't re-render the whole guide. */
function GuideMacros({ control }: { control: GuideControl }) {
  const [calories, protein, carbs, fat] = useWatch({ control, name: ["calories", "protein", "carbs", "fat"] })
  return <MacroSummary calories={calories} protein={protein} carbs={carbs} fat={fat} />
}

/** How the targets were reached, or that they're the general ones when no estimate came back. */
function EstimateNote({ estimate }: { estimate: TargetEstimate | null }) {
  if (!estimate) return <p className="text-sm text-muted-foreground">These are general starting targets: yours couldn’t be estimated just now.</p>
  const { resting, maintenance, adjustment } = estimate
  const forGoal = adjustment === 0 ? "" : `, ${adjustment > 0 ? "+" : "−"}${formatNumber(Math.abs(adjustment))} kcal a day for your goal`
  return (
    <p className="text-sm text-muted-foreground">
      Estimated for you: {formatNumber(resting)} kcal a day at rest, {formatNumber(maintenance)} kcal to maintain with your activity{forGoal}.
    </p>
  )
}

function Choice({ legend, description, error, children }: { legend: string; description?: string; error?: string; children: ReactNode }) {
  return (
    <FieldSet className="gap-2">
      <FieldLegend variant="label">{legend}</FieldLegend>
      {children}
      {error ? <FieldError>{error}</FieldError> : description ? <FieldDescription>{description}</FieldDescription> : null}
    </FieldSet>
  )
}
