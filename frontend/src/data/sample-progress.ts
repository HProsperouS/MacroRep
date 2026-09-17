import { addDays, differenceInCalendarDays, format, startOfWeek, subDays } from "date-fns"

import type { CheckInHistoryItem, ProgressRange, StrengthLift, VolumeWeek, WeightPoint } from "@/types/progress"

/** Deterministic sample series for the mock API. Values are illustrative only. */

const HISTORY_DAYS = 420
export const RANGE_DAYS: Record<ProgressRange, number> = { "1M": 24, "3M": 90, "6M": 180, "1Y": 365, All: HISTORY_DAYS }

const dayKey = (date: Date) => format(date, "yyyy-MM-dd")

/** Trend falls ~0.05 kg/day over the last 8 weeks, slower before that. Ends at 72.0 kg today. */
function trendAt(daysAgo: number) {
  if (daysAgo <= 56) return 72 + daysAgo * 0.05
  return 72 + 56 * 0.05 + (daysAgo - 56) * 0.012
}

/** Pseudo-random but stable noise between -0.6 and 0.6 kg. */
function noise(daysAgo: number) {
  return Math.sin(daysAgo * 12.9898) * 0.6
}

export function buildWeightSeries(today = new Date()): WeightPoint[] {
  const points: WeightPoint[] = []
  for (let daysAgo = HISTORY_DAYS - 1; daysAgo >= 0; daysAgo--) {
    const trend = Math.round(trendAt(daysAgo) * 10) / 10
    // Skip roughly one weigh-in a week, and today (so Home shows the reminder).
    const skipped = daysAgo === 0 || daysAgo % 7 === 3
    points.push({
      date: dayKey(subDays(today, daysAgo)),
      scaleKg: skipped ? null : Math.round((trendAt(daysAgo) + noise(daysAgo)) * 10) / 10,
      trendKg: trend,
    })
  }
  return points
}

export function buildVolumeWeeks(days: number, today = new Date()): VolumeWeek[] {
  const weeks = Math.max(4, Math.ceil(days / 7))
  const thisWeek = startOfWeek(today, { weekStartsOn: 1 })
  return Array.from({ length: weeks }, (_, index) => {
    const weeksAgo = weeks - 1 - index
    const base = 19.2 - weeksAgo * 0.12
    const wobble = Math.cos(weeksAgo * 1.7) * 1.1
    return {
      weekStart: dayKey(addDays(thisWeek, -7 * weeksAgo)),
      tonnes: Math.max(8, Math.round((weeksAgo === 0 ? 19.2 : base + wobble) * 10) / 10),
    }
  })
}

export const SAMPLE_STRENGTH: StrengthLift[] = [
  { exercise: "Bench press", estimated1RmKg: 76, changeKg: 4 },
  { exercise: "Back squat", estimated1RmKg: 105, changeKg: 7.5 },
  { exercise: "Deadlift", estimated1RmKg: 132, changeKg: 5 },
  { exercise: "Overhead press", estimated1RmKg: 47, changeKg: 1.5 },
]

export function buildCheckInHistory(today = new Date()): CheckInHistoryItem[] {
  return [
    { id: "ci-37", weekLabel: "Week 37", date: dayKey(subDays(today, 9)), summary: "Calories 2,450 → 2,350 · Squat +5 kg", outcome: "applied" },
    { id: "ci-36", weekLabel: "Week 36", date: dayKey(subDays(today, 16)), summary: "No changes proposed", outcome: "no-changes" },
    { id: "ci-35", weekLabel: "Week 35", date: dayKey(subDays(today, 23)), summary: "Protein 150 → 165 g · Added 2 back sets", outcome: "edited" },
    { id: "ci-34", weekLabel: "Week 34", date: dayKey(subDays(today, 30)), summary: "Carbs 280 → 250 g on rest days", outcome: "rejected" },
  ]
}

export function withinRange(date: string, days: number, today = new Date()) {
  return differenceInCalendarDays(today, new Date(`${date}T00:00:00`)) < days
}

/** Calories logged on previous days; today's value comes from the live food log. */
export const PAST_DAILY_CALORIES = [2280, 2410, 2195, 2360, 2520, 2240]
