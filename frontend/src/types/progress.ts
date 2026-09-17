export const PROGRESS_RANGES = ["1M", "3M", "6M", "1Y", "All"] as const
export type ProgressRange = (typeof PROGRESS_RANGES)[number]

export type WeightPoint = {
  /** yyyy-MM-dd */
  date: string
  /** Null on days without a weigh-in. */
  scaleKg: number | null
  trendKg: number
}

export type VolumeWeek = {
  /** yyyy-MM-dd, Monday of the week */
  weekStart: string
  tonnes: number
}

export type StrengthLift = {
  exercise: string
  estimated1RmKg: number
  changeKg: number
}

export type CheckInOutcome = "applied" | "edited" | "rejected" | "no-changes"

export type CheckInHistoryItem = {
  id: string
  weekLabel: string
  /** yyyy-MM-dd */
  date: string
  summary: string
  outcome: CheckInOutcome
}

export type ProgressResponse = {
  range: ProgressRange
  from: string
  to: string
  weight: {
    points: WeightPoint[]
    currentTrendKg: number
    changeKg: number
    ratePerWeekKg: number
    goalRatePerWeekKg: number
  }
  expenditureKcalPerDay: number
  adherencePercent: number
  workouts: { done: number; planned: number }
  volume: { weeks: VolumeWeek[]; targetTonnes: number; changePercent: number }
  strength: StrengthLift[]
  checkIns: CheckInHistoryItem[]
}

export type DailyCalories = {
  date: string
  calories: number
}

export type WeighInInput = {
  date: string
  weightKg: number
}
