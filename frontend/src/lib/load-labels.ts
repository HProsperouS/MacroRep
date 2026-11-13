import { formatNumber } from "@/lib/format"
import type { HistoryExercise } from "@/types/workout"

/** "60 kg × 8"; "BW × 12" or "BW + 10 kg × 8" for a bodyweight move (the kg is what was added);
 *  "Band × 15" for a band, whose kg is a guess and isn't shown. */
export function setLoadLabel(equipment: HistoryExercise["equipment"], weightKg: number, reps: number) {
  if (equipment === "band") return `Band × ${reps}`
  if (equipment === "bodyweight") return weightKg > 0 ? `BW + ${formatNumber(weightKg, 2)} kg × ${reps}` : `BW × ${reps}`
  return `${formatNumber(weightKg, 2)} kg × ${reps}`
}

/** " · 45 band reps", or nothing without band work: band sets have no load for kg volume to count. */
export function bandRepsSuffix(repBasedReps: number | undefined) {
  return repBasedReps ? ` · ${formatNumber(repBasedReps)} band reps` : ""
}

/** "Bodyweight counted at 72 kg" when a workout with bodyweight moves had a weigh-in to use. */
export function bodyWeightNote(bodyWeightKg: number | null | undefined, exercises: Pick<HistoryExercise, "equipment">[] | undefined) {
  if (bodyWeightKg == null || !exercises?.some((exercise) => exercise.equipment === "bodyweight")) return null
  return `Bodyweight counted at ${formatNumber(bodyWeightKg, 1)} kg`
}
