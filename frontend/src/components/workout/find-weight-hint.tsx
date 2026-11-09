import { Compass } from "lucide-react"

import { FIRST_SET_REPS_IN_RESERVE, findWeightStep, TARGET_RPE } from "@/lib/find-weight"
import type { SessionExercise } from "@/lib/workout-session"

/** Guidance for an exercise with nothing to go on: start light, rate the set, then adjust by effort. */
export function FindWeightHint({ exercise }: { exercise: SessionExercise }) {
  if (!exercise.finding) return null
  const step = findWeightStep(exercise.sets)
  if (!step) return null

  return (
    <div role="note" className="flex items-start gap-2 rounded-lg bg-primary/7 p-3 text-sm">
      <Compass className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
      <div className="flex flex-col gap-1">
        {step.step === "start" ? (
          <>
            <p className="font-medium">New for you? Find your weight by feel.</p>
            <p className="text-muted-foreground">
              Start light: pick a weight where you could do about {FIRST_SET_REPS_IN_RESERVE} more reps than
              {step.reps ? ` the ${step.reps} planned` : " you plan"}. Do the set, then enter how hard it felt as an
              RPE: 10 means nothing left, 9 one more rep, {TARGET_RPE} two more. We'll suggest the next weight.
            </p>
          </>
        ) : step.step === "rate" ? (
          <p className="text-muted-foreground">
            Enter an RPE for the set you just did and we'll tell you whether to go up or down.
          </p>
        ) : (
          <p>
            <span className="font-medium">{step.advice.message}</span>
            <span className="block text-muted-foreground">
              Aim for about RPE {TARGET_RPE}. It's an estimate, so trust how the set felt over the number.
            </span>
          </p>
        )}
      </div>
    </div>
  )
}
