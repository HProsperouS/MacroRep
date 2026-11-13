import { formatNumber } from "@/lib/format"
import { setLoadLabel } from "@/lib/load-labels"
import { cn } from "@/lib/utils"
import { historySetLabels } from "@/lib/workout-session"
import type { HistoryExercise } from "@/types/workout"

/** One logged exercise and its sets: "Set 1  60 kg × 8  RPE 8". Shared by history, the
 *  post-workout summary and Home's "Done today". */
export function ExerciseSets({ exercise, compact = false }: { exercise: HistoryExercise; compact?: boolean }) {
  // Only working sets are numbered, so "Set 1" is always the first working set.
  const labels = historySetLabels(exercise.sets)
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">{exercise.name}</h3>
      <ul className="divide-y">
        {exercise.sets.map((set, index) => (
          <li key={index} className={cn("flex items-center gap-3 text-sm", compact ? "py-1" : "py-1.5")}>
            <span className="w-20 shrink-0 text-muted-foreground">{labels[index]}</span>
            <span className="flex-1 tabular-nums">{setLoadLabel(exercise.equipment, set.weightKg, set.reps)}</span>
            {set.rpe != null ? <span className="shrink-0 text-muted-foreground tabular-nums">RPE {formatNumber(set.rpe, 1)}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
