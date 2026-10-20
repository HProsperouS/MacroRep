import type { ProgressResponse } from "@/types/progress"

export function progressResponse(overrides: Partial<ProgressResponse> = {}): ProgressResponse {
  return {
    range: "1M",
    from: "2026-09-21",
    to: "2026-10-20",
    weight: {
      points: [
        { date: "2026-10-18", scaleKg: 80.4, trendKg: 80.6 },
        { date: "2026-10-19", scaleKg: 80.0, trendKg: 80.5 },
        { date: "2026-10-20", scaleKg: null, trendKg: 80.4 },
      ],
      currentTrendKg: 80.4,
      changeKg: -1.2,
      ratePerWeekKg: -0.3,
      goalRatePerWeekKg: -0.5,
    },
    expenditureKcalPerDay: 2650,
    adherencePercent: 90,
    logging: { completeDays: 25, partialDays: 2, missingDays: 3, targetAdherencePercent: 70, targetGapKcal: -5400 },
    workouts: { done: 10, planned: 12, completionPercent: 83.3 },
    volume: {
      weeks: [
        { weekStart: "2026-10-06", tonnes: 12.5, avgRpe: 7.5 },
        { weekStart: "2026-10-13", tonnes: 14, avgRpe: null },
      ],
      averageTonnes: 13.25,
      targetTonnes: null,
      lastWeekTonnes: 14,
      changePercent: 12,
    },
    rpe: { thisWeekAvg: 8, change: 0.5 },
    strength: [{ exercise: "Bench Press", estimated1RmKg: 92.5, changeKg: 2.5 }],
    checkIns: [{ id: "c1", weekLabel: "Week 3", date: "2026-10-13", summary: "Raised calories by 150.", outcome: "applied" }],
    ...overrides,
  }
}
