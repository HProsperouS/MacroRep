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
  /** Mean RPE of the week's working sets with an RPE logged; null if none was. */
  avgRpe: number | null
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

/**
 * How fully a day was logged. Partial = under half the calorie target; it still counts as eaten.
 * Today is in progress until it ends.
 */
export type DayStatus = "complete" | "partial" | "missing" | "in-progress"

/** Finished days only: today isn't counted. */
export type LoggingSummary = {
  completeDays: number
  partialDays: number
  missingDays: number
  /** Logged days within ±10% of the calorie target; null with nothing logged. */
  targetAdherencePercent: number | null
  /** Intake minus target summed over logged days: negative means under target. */
  targetGapKcal: number
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
  /** Share of finished days with any food logged. */
  adherencePercent: number
  logging: LoggingSummary
  workouts: {
    /** Every logged session, planned or not. */
    done: number
    /** Plan days that fell due in the range; today only once trained. */
    planned: number
    /** done / planned, not capped at 100; null with nothing planned. */
    completionPercent: number | null
  }
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
  rpe: {
    /** Average RPE over the current Monday–Sunday week so far; null until one is logged. */
    thisWeekAvg: number | null
    /** RPE points vs last week; null unless both weeks have RPE logged. */
    change: number | null
  }
  strength: StrengthLift[]
  checkIns: CheckInHistoryItem[]
}

export type DailyCalories = {
  date: string
  calories: number
  status: DayStatus
}

export type DailyCaloriesResponse = {
  days: DailyCalories[]
  targetCalories: number
  /** Intake minus target over the finished logged days: negative means under target. */
  targetGapKcal: number
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
