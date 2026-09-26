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
  volume: {
    weeks: VolumeWeek[]
    /** Mean of the weeks in range: a reference line, not a goal. */
    averageTonnes: number
    /** A weekly volume goal; null until one exists. Shown instead of the average when set. */
    targetTonnes: number | null
    /** The most recent completed Monday–Sunday week. */
    lastWeekTonnes: number
    /** lastWeekTonnes vs the week before it; null when that week had no volume. */
    changePercent: number | null
  }
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

/** A stored weigh-in, as listed for editing. */
export type WeighIn = WeighInInput & {
  id: string
  trendKg: number
}
