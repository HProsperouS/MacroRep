import { createRequestId } from "@/api/client"
import { buildSampleCheckIn } from "@/data/sample-coach"
import { SAMPLE_EXERCISES } from "@/data/sample-exercises"
import { SAMPLE_ENTRIES, SAMPLE_FOODS, SAMPLE_TARGETS } from "@/data/sample-food"
import { buildWeightSeries } from "@/data/sample-progress"
import type { FoodEntry } from "@/types/food"
import type { Profile } from "@/types/profile"

/** In-memory state shared by the mock routes. Resets on page reload. */

export const todayKey = new Date().toLocaleDateString("en-CA") // yyyy-MM-dd

const profile: Profile = {
  name: "Alex Tan",
  email: "alex.tan@example.com",
  heightCm: 175,
  goal: "lose",
  weeklyRateKg: -0.5,
  trainingDaysPerWeek: 3,
}

export const db = {
  entries: new Map<string, (FoodEntry & { date: string })[]>([
    [todayKey, SAMPLE_ENTRIES.map((entry) => ({ ...entry, id: createRequestId(), date: todayKey }))],
  ]),
  foods: [...SAMPLE_FOODS],
  targets: { ...SAMPLE_TARGETS },
  weights: buildWeightSeries(),
  checkIn: buildSampleCheckIn(),
  exercises: structuredClone(SAMPLE_EXERCISES),
  workoutFinishedToday: false,
  profile,
}

export type MockHandler = (ctx: { params: Record<string, string>; query: Record<string, unknown>; body: unknown }) => [number, unknown?]
export type MockRoute = { method: string; pattern: RegExp; handler: MockHandler }
