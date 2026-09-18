import { Play, Zap } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useActiveWorkout } from "@/hooks/use-active-workout"
import { beginWorkout } from "@/lib/active-workout-store"
import type { PlannedWorkout } from "@/types/workout"

type StartWorkoutButtonProps = {
  plan: PlannedWorkout | null | undefined
  className?: string
}

/** "Resume workout" when one is in progress; otherwise starts today's plan (or opens the chooser). */
export function StartWorkoutButton({ plan, className }: StartWorkoutButtonProps) {
  const active = useActiveWorkout()
  const navigate = useNavigate()

  if (active || !plan) {
    return (
      <Button className={className} asChild>
        <Link to="/workout">
          {active ? <Play data-icon="inline-start" /> : <Zap data-icon="inline-start" />}
          {active ? "Resume workout" : "Start workout"}
        </Link>
      </Button>
    )
  }

  return (
    <Button
      className={className}
      onClick={() => {
        beginWorkout(plan)
        navigate("/workout")
      }}
    >
      <Zap data-icon="inline-start" />
      Start workout
    </Button>
  )
}
