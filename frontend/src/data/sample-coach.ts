import { format, subDays } from "date-fns"

import type { CheckIn } from "@/types/coach"

/** Sample weekly check-in for the mock API. Matches the design canvas. */
export function buildSampleCheckIn(today = new Date()): CheckIn {
  const start = subDays(today, 6)
  return {
    id: "ci-38",
    weekLabel: "Week 38",
    rangeLabel: `${format(start, "d")}–${format(today, "d MMMM")}`,
    status: "needs-review",
    summary:
      "Weight is trending down at 0.35 kg/week, a bit slower than your 0.5 kg goal. Training is progressing well: you completed 3 of 3 sessions and beat last week’s bench press volume.",
    stats: [
      { label: "Trend change", value: "−0.35 kg" },
      { label: "Avg intake", value: "2,310 kcal" },
      { label: "Expenditure", value: "2,480 kcal" },
      { label: "Days logged", value: "7 / 7" },
      { label: "Workouts", value: "3 / 3" },
    ],
    pipeline: [
      { id: "data", title: "Data gathered", detail: "7 days · 21 meals · 6 weigh-ins · 3 workouts", status: "done" },
      { id: "nutrition", title: "Nutrition agent", detail: "Expenditure & calorie target", status: "done" },
      { id: "workout", title: "Workout agent", detail: "Progression & volume", status: "done" },
      { id: "reviewer", title: "Reviewer", detail: "Safety & consistency checks passed", status: "done" },
      { id: "approval", title: "Your approval", detail: "2 changes waiting", status: "waiting" },
    ],
    proposals: [
      {
        id: "p-nutrition",
        kind: "nutrition",
        headline: "Lower daily calories slightly to get back on your −0.5 kg/week pace.",
        changes: [
          { id: "calories", label: "Calories", unit: "kcal", before: 2350, after: 2200, step: 10 },
          { id: "protein", label: "Protein", unit: "g", before: 165, after: 165, step: 1 },
          { id: "carbs", label: "Carbs", unit: "g", before: 250, after: 215, step: 1 },
        ],
        evidence: [
          "Trend weight fell 0.35 kg this week, below your 0.5 kg target.",
          "Estimated expenditure is steady at ~2,480 kcal/day.",
          "You logged 7 of 7 days (avg 2,310 kcal).",
        ],
        reviewerNote: "Change is 6.4%, inside the 10% weekly limit. Protein floor kept.",
        status: "pending",
      },
      {
        id: "p-training",
        kind: "training",
        headline: "Add load on bench press — you hit the top of the rep range twice.",
        changes: [
          { id: "bench", label: "Bench press", unit: "kg", before: 60, after: 62.5, step: 2.5 },
          { id: "cable-row", label: "Cable row", unit: "kg", before: 52.5, after: 52.5, step: 2.5 },
        ],
        evidence: [
          `3 × 8 at 60 kg completed on ${format(subDays(today, 6), "d MMM")} and ${format(subDays(today, 2), "d MMM")}.`,
          "Weekly chest volume is within your plan (12 sets).",
        ],
        reviewerNote: "Consistent with double progression rule. No recovery flags.",
        status: "pending",
      },
    ],
    suggestedQuestions: ["Why not a bigger cut?", "Keep carbs on leg day", "Show the expenditure estimate"],
  }
}

/** Canned, data-grounded replies. The real coach agent only answers about this check-in. */
export function coachReply(question: string) {
  const q = question.toLowerCase()
  if (q.includes("bigger") || q.includes("cut") || q.includes("faster")) {
    return "A bigger cut would be more than the 10% weekly limit the reviewer enforces. Dropping 150 kcal should bring your trend from −0.35 to about −0.5 kg/week while keeping protein at 165 g to protect muscle."
  }
  if (q.includes("carb") || q.includes("leg")) {
    return "I can keep carbs higher on leg day. One option: 250 g on training days and 190 g on rest days, which averages about the same weekly intake as the proposal. Use Edit on the nutrition card to set the daily target you prefer."
  }
  if (q.includes("expenditure") || q.includes("tdee") || q.includes("burn")) {
    return "Your expenditure estimate is ~2,480 kcal/day. It comes from your average intake (2,310 kcal) plus the energy implied by the trend weight change over the last 3 weeks."
  }
  return "I can only answer questions about this check-in: your logged food, weigh-ins, workouts and the proposed changes. Try asking about the calorie change or the bench press progression."
}
