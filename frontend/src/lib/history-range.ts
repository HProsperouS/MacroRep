import { format, isValid, parseISO, subDays } from "date-fns"

import type { HistoryRange } from "@/types/workout"

export const HISTORY_PRESETS = ["all", "today", "week", "month", "custom"] as const
export type HistoryPreset = (typeof HISTORY_PRESETS)[number]

export const HISTORY_PRESET_LABELS: Record<HistoryPreset, string> = {
  all: "All",
  today: "Today",
  week: "Past week",
  month: "Past month",
  custom: "Custom",
}

export const dayKey = (day: Date) => format(day, "yyyy-MM-dd")

export function isHistoryPreset(value: string | null): value is HistoryPreset {
  return (HISTORY_PRESETS as readonly string[]).includes(value ?? "")
}

function isDay(value: string | undefined): value is string {
  return value !== undefined && /^\d{4}-\d{2}-\d{2}$/.test(value) && isValid(parseISO(value))
}

/** The days a preset covers, ending today. "Past week" is the last 7 days including today,
 *  "Past month" the last 30. A custom range uses whichever of its ends is a real date. */
export function rangeFor(preset: HistoryPreset, today: Date, custom: HistoryRange = {}): HistoryRange {
  const end = dayKey(today)
  switch (preset) {
    case "all":
      return {}
    case "today":
      return { from: end, to: end }
    case "week":
      return { from: dayKey(subDays(today, 6)), to: end }
    case "month":
      return { from: dayKey(subDays(today, 29)), to: end }
    case "custom":
      return { ...(isDay(custom.from) ? { from: custom.from } : {}), ...(isDay(custom.to) ? { to: custom.to } : {}) }
  }
}

/** A custom range whose start is after its end can't match anything; say so instead of asking. */
export function rangeError(range: HistoryRange) {
  return range.from && range.to && range.from > range.to ? "The start date is after the end date." : null
}
