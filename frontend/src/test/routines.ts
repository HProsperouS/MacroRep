import type { PlannedExercise, Routine } from "@/types/workout"

export function plannedExercise(id: string, name: string): PlannedExercise {
  return {
    id,
    name,
    equipment: "Barbell",
    muscles: "Chest",
    restSeconds: 90,
    sets: [
      { id: `${id}-0`, kind: "warmup", targetWeightKg: 40, targetReps: 10 },
      { id: `${id}-1`, kind: "working", targetWeightKg: 60, targetReps: 8 },
    ],
  }
}

export function routine(id: string, name: string, scheduledDays: number[] = [], exercises: PlannedExercise[] = [plannedExercise("bench", "Bench Press")]): Routine {
  return { id, name, estimatedMinutes: 45, exercises, scheduledDays }
}
