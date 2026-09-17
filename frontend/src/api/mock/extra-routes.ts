import { format, subDays } from "date-fns"

import { createRequestId } from "@/api/client"
import { db, todayKey, type MockRoute } from "@/api/mock/mock-db"
import { coachReply } from "@/data/sample-coach"
import { buildCheckInHistory, buildVolumeWeeks, PAST_DAILY_CALORIES, RANGE_DAYS, SAMPLE_STRENGTH, withinRange } from "@/data/sample-progress"
import { SAMPLE_WORKOUT } from "@/data/sample-workout"
import type { DailyTargets } from "@/types/food"
import type { ProposalDecisionInput } from "@/types/coach"
import { PROGRESS_RANGES, type ProgressRange, type ProgressResponse, type WeighInInput } from "@/types/progress"
import type { UpdateProfileInput } from "@/types/profile"
import { EQUIPMENT, MUSCLE_GROUPS, type CreateExerciseInput, type Exercise, type FinishWorkoutInput, type WorkoutSummary } from "@/types/workout"

/** Mock routes for Home, Workout, Coach, Progress and Profile. */

const round1 = (value: number) => Math.round(value * 10) / 10

function isPositiveNumber(value: unknown, max: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0 && value <= max
}

export const extraRoutes: MockRoute[] = [
  // ── Nutrition ───────────────────────────────────────────────
  {
    method: "put",
    pattern: /^\/nutrition\/targets$/,
    handler: ({ body }) => {
      const input = body as DailyTargets
      if (!isPositiveNumber(input.calories, 10_000)) return [422, { detail: "Calories must be between 1 and 10,000" }]
      db.targets = { calories: input.calories, protein: input.protein, carbs: input.carbs, fat: input.fat }
      return [200, db.targets]
    },
  },
  {
    method: "get",
    pattern: /^\/nutrition\/daily-calories$/,
    handler: ({ query }) => {
      const days = Math.min(Number(query.days ?? 7), PAST_DAILY_CALORIES.length + 1)
      const today = new Date()
      const todayCalories = (db.entries.get(todayKey) ?? []).reduce((sum, entry) => sum + entry.calories, 0)
      const series = [...PAST_DAILY_CALORIES, todayCalories].slice(-days)
      return [200, series.map((calories, index) => ({ date: format(subDays(today, series.length - 1 - index), "yyyy-MM-dd"), calories }))]
    },
  },

  // ── Workouts ───────────────────────────────────────────────
  {
    method: "get",
    pattern: /^\/workouts\/today$/,
    handler: () => [200, SAMPLE_WORKOUT],
  },
  {
    method: "post",
    pattern: /^\/workouts\/sessions$/,
    handler: ({ body }) => {
      const input = body as FinishWorkoutInput
      const sets = input.exercises.flatMap((exercise) => exercise.sets)
      if (sets.length === 0) return [422, { detail: "Complete at least one set before finishing" }]
      const volumeKg = sets.filter((set) => set.kind === "working").reduce((sum, set) => sum + set.weightKg * set.reps, 0)
      const durationSeconds = Math.max(0, Math.round((Date.parse(input.finishedAt) - Date.parse(input.startedAt)) / 1000))
      const bench = input.exercises.find((exercise) => exercise.exerciseId === "bench")
      const benchPr = bench?.sets.some((set) => set.kind === "working" && set.weightKg * (1 + set.reps / 30) > 76)
      db.workoutFinishedToday = true
      // Remember these sets as each exercise's "last session".
      const today = format(new Date(), "yyyy-MM-dd")
      for (const logged of input.exercises) {
        const exercise = db.exercises.find((e) => e.id === logged.exerciseId)
        const working = logged.sets.filter((set) => set.kind === "working")
        if (exercise && working.length > 0) exercise.lastSession = { date: today, sets: working.map(({ weightKg, reps }) => ({ weightKg, reps })) }
      }
      const summary: WorkoutSummary = {
        id: createRequestId(),
        name: input.name || SAMPLE_WORKOUT.name,
        durationSeconds,
        setsCompleted: sets.length,
        volumeKg: Math.round(volumeKg),
        personalRecords: benchPr ? ["Bench press · new estimated 1RM"] : [],
      }
      return [201, summary]
    },
  },

  {
    method: "get",
    pattern: /^\/exercises$/,
    handler: ({ query }) => {
      const q = String(query.q ?? "").trim().toLowerCase()
      const muscle = query.muscle ? String(query.muscle) : undefined
      const equipment = query.equipment ? String(query.equipment) : undefined
      const limit = Math.min(Number(query.limit ?? 30), 100)
      const matches = db.exercises
        .filter((exercise) => (!q || exercise.name.toLowerCase().includes(q)) && (!muscle || exercise.muscles.includes(muscle as Exercise["muscles"][number])) && (!equipment || exercise.equipment === equipment))
        // Custom exercises first, then alphabetical.
        .toSorted((a, b) => (a.source === b.source ? a.name.localeCompare(b.name) : a.source === "custom" ? -1 : 1))
      return [200, matches.slice(0, limit)]
    },
  },
  {
    method: "post",
    pattern: /^\/exercises$/,
    handler: ({ body }) => {
      const input = body as CreateExerciseInput
      const name = input.name?.trim()
      if (!name) return [422, { detail: "Exercise name is required" }]
      if (!EQUIPMENT.includes(input.equipment)) return [422, { detail: "Choose the equipment" }]
      if (!input.muscles?.length || input.muscles.some((m) => !MUSCLE_GROUPS.includes(m))) return [422, { detail: "Choose at least one muscle group" }]
      if (db.exercises.some((exercise) => exercise.name.toLowerCase() === name.toLowerCase())) return [409, { detail: `“${name}” already exists — search for it instead` }]
      const created: Exercise = { id: createRequestId(), name, equipment: input.equipment, muscles: input.muscles, source: "custom" }
      db.exercises = [created, ...db.exercises]
      return [201, created]
    },
  },

  // ── Progress & body ────────────────────────────────────────
  {
    method: "get",
    pattern: /^\/progress$/,
    handler: ({ query }) => {
      const range = String(query.range ?? "1M") as ProgressRange
      if (!PROGRESS_RANGES.includes(range)) return [422, { detail: "Unknown range" }]
      const days = RANGE_DAYS[range]
      const points = db.weights.filter((point) => withinRange(point.date, days))
      const first = points[0]
      const last = points[points.length - 1]
      const changeKg = round1(last.trendKg - first.trendKg)
      const weeks = Math.max(1, (points.length - 1) / 7)
      const weekCount = Math.ceil(days / 7)
      const response: ProgressResponse = {
        range,
        from: first.date,
        to: last.date,
        weight: {
          points,
          currentTrendKg: last.trendKg,
          changeKg,
          ratePerWeekKg: Math.round((changeKg / weeks) * 100) / 100,
          goalRatePerWeekKg: db.profile.weeklyRateKg,
        },
        expenditureKcalPerDay: 2480,
        adherencePercent: range === "1M" ? 86 : 81,
        workouts: { done: weekCount * 3 - Math.ceil(weekCount / 4), planned: weekCount * 3 },
        volume: { weeks: buildVolumeWeeks(days), targetTonnes: 18, changePercent: 7 },
        strength: SAMPLE_STRENGTH,
        checkIns: buildCheckInHistory().filter((item) => withinRange(item.date, days)),
      }
      return [200, response]
    },
  },
  {
    method: "post",
    pattern: /^\/body\/weigh-ins$/,
    handler: ({ body }) => {
      const input = body as WeighInInput
      if (!isPositiveNumber(input.weightKg, 400)) return [422, { detail: "Enter a weight between 1 and 400 kg" }]
      const point = db.weights.find((p) => p.date === input.date)
      if (!point) return [422, { detail: "Weigh-ins can only be added for the last year" }]
      point.scaleKg = round1(input.weightKg)
      // Exponentially smoothed trend, as the backend would compute it.
      const index = db.weights.indexOf(point)
      const previous = db.weights[index - 1]?.trendKg ?? point.scaleKg
      point.trendKg = round1(previous + 0.1 * (point.scaleKg - previous))
      return [201, point]
    },
  },

  // ── Coach ──────────────────────────────────────────────────
  {
    method: "get",
    pattern: /^\/coach\/check-ins\/current$/,
    handler: () => [200, db.checkIn],
  },
  {
    method: "post",
    pattern: /^\/coach\/check-ins\/(?<checkInId>[^/]+)\/proposals\/(?<proposalId>[^/]+)\/decision$/,
    handler: ({ params, body }) => {
      const checkIn = db.checkIn
      if (checkIn.id !== params.checkInId) return [404, { detail: "Check-in not found" }]
      const proposal = checkIn.proposals.find((p) => p.id === params.proposalId)
      if (!proposal) return [404, { detail: "Proposal not found" }]
      if (proposal.status !== "pending") return [409, { detail: "This proposal has already been decided" }]

      const input = body as ProposalDecisionInput
      if (input.decision === "reject") {
        proposal.status = "rejected"
      } else {
        for (const change of input.changes ?? []) {
          const target = proposal.changes.find((c) => c.id === change.id)
          if (!target) return [422, { detail: `Unknown change ${change.id}` }]
          if (!(change.after > 0)) return [422, { detail: `${target.label} must be greater than 0` }]
        }
        const edited = input.changes?.some((change) => proposal.changes.find((c) => c.id === change.id)?.after !== change.after) ?? false
        for (const change of input.changes ?? []) {
          const target = proposal.changes.find((c) => c.id === change.id)
          if (target) target.after = change.after
        }
        proposal.status = edited ? "edited" : "applied"
        if (proposal.kind === "nutrition") {
          for (const change of proposal.changes) {
            if (change.id in db.targets) db.targets[change.id as keyof DailyTargets] = change.after
          }
        }
      }

      const waiting = checkIn.proposals.filter((p) => p.status === "pending").length
      const approval = checkIn.pipeline.find((step) => step.id === "approval")
      if (approval) {
        approval.status = waiting === 0 ? "done" : "waiting"
        approval.detail = waiting === 0 ? "All changes reviewed" : `${waiting} change${waiting === 1 ? "" : "s"} waiting`
      }
      if (waiting === 0) checkIn.status = "reviewed"
      return [200, proposal]
    },
  },
  {
    method: "post",
    pattern: /^\/coach\/check-ins\/(?<checkInId>[^/]+)\/messages$/,
    handler: ({ params, body }) => {
      if (db.checkIn.id !== params.checkInId) return [404, { detail: "Check-in not found" }]
      const text = String((body as { text?: unknown }).text ?? "").trim()
      if (!text) return [422, { detail: "Ask a question first" }]
      if (text.length > 500) return [422, { detail: "Keep questions under 500 characters" }]
      return [200, { id: createRequestId(), role: "coach", text: coachReply(text) }]
    },
  },

  // ── Profile ────────────────────────────────────────────────
  {
    method: "get",
    pattern: /^\/profile$/,
    handler: () => [200, db.profile],
  },
  {
    method: "put",
    pattern: /^\/profile$/,
    handler: ({ body }) => {
      const input = body as UpdateProfileInput
      if (!input.name?.trim()) return [422, { detail: "Name is required" }]
      db.profile = { ...db.profile, ...input, name: input.name.trim() }
      return [200, db.profile]
    },
  },
]
