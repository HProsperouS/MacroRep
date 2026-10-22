import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { nutritionProposal } from "@/components/coach/proposal-fixtures"
import { clearActiveWorkout, getActiveWorkout } from "@/lib/active-workout-store"
import HomePage from "@/pages/home-page"
import { progressResponse } from "@/test/progress"
import { renderPage } from "@/test/render"
import { plannedExercise, routine } from "@/test/routines"
import type { FoodEntry } from "@/types/food"

const foodApi = vi.hoisted(() => ({ getFoodLog: vi.fn(), getTargets: vi.fn() }))
const progressApi = vi.hoisted(() => ({ getProgress: vi.fn(), getDailyCalories: vi.fn(), addWeighIn: vi.fn() }))
const workoutApi = vi.hoisted(() => ({ getToday: vi.fn() }))
const coachApi = vi.hoisted(() => ({ getCurrentCheckIn: vi.fn() }))
vi.mock("@/api/food-api", () => ({ foodApi }))
vi.mock("@/api/progress-api", () => ({ progressApi }))
vi.mock("@/api/workout-api", () => ({ workoutApi }))
vi.mock("@/api/coach-api", () => ({ coachApi }))
vi.mock("@/hooks/use-media-query")

const lunch: FoodEntry = { id: "e1", meal: "lunch", name: "Chicken rice", amountLabel: "1 plate", source: "quick-add", calories: 600, protein: 25, carbs: 80, fat: 20 }

const plan = {
  ...routine("r-push", "Push day", [], ["bench", "ohp", "dips", "flies"].map((id) => plannedExercise(id, id.toUpperCase()))),
}

beforeEach(() => {
  // 16:00 local time on a Tuesday: breakfast and lunch are due, dinner isn't yet.
  vi.useFakeTimers({ toFake: ["Date"] })
  vi.setSystemTime(new Date(2026, 9, 20, 16, 0))
  clearActiveWorkout()
  foodApi.getFoodLog.mockResolvedValue({ date: "2026-10-20", entries: [lunch] })
  foodApi.getTargets.mockResolvedValue({ calories: 2200, protein: 150, carbs: 250, fat: 70 })
  progressApi.getProgress.mockResolvedValue(progressResponse())
  progressApi.getDailyCalories.mockResolvedValue({
    days: [
      { date: "2026-10-18", calories: 2100, status: "complete", targetCalories: 2200 },
      { date: "2026-10-19", calories: 900, status: "partial", targetCalories: 2200 },
      { date: "2026-10-20", calories: 600, status: "in-progress", targetCalories: 2200 },
    ],
    targetCalories: 2200,
    targetGapKcal: -1400,
  })
  workoutApi.getToday.mockResolvedValue(plan)
  coachApi.getCurrentCheckIn.mockResolvedValue({ id: "c1", status: "needs-review", proposals: [nutritionProposal(), nutritionProposal({ id: "p2", status: "applied" })] })
})

afterEach(() => {
  vi.useRealTimers()
})

describe("HomePage", () => {
  it("summarises today's nutrition, weight trend and planned workout", async () => {
    renderPage(<HomePage />)

    expect(await screen.findByText("1,600")).toBeInTheDocument()
    expect(screen.getByText("kcal left")).toBeInTheDocument()
    expect(screen.queryByText(/Burned/)).not.toBeInTheDocument() // not something the logs can tell
    expect(screen.getByText("80.4")).toBeInTheDocument()
    expect(screen.getByText("−0.3 kg / wk")).toBeInTheDocument()
    expect(await screen.findByText("Push day")).toBeInTheDocument()
    expect(screen.getByText("4 exercises · 8 sets · ~45 min")).toBeInTheDocument()
    expect(screen.getByText("+1 more")).toBeInTheDocument()
    expect(await screen.findByText("1,400 kcal")).toBeInTheDocument()
    expect(screen.getByText(/under target across 2 logged days · 1 under half the target/)).toBeInTheDocument()
  })

  it("shows no trend weight before the first weigh-in, rather than 0", async () => {
    const response = progressResponse()
    progressApi.getProgress.mockResolvedValue({
      ...response,
      weight: { ...response.weight, points: response.weight.points.map((point) => ({ ...point, scaleKg: null, trendKg: null })), currentTrendKg: null, ratePerWeekKg: null },
    })
    renderPage(<HomePage />)

    const card = (await screen.findByText("Trend weight")).closest("[data-slot=card]") as HTMLElement
    expect(await within(card).findByText("—")).toBeInTheDocument()
    expect(within(card).queryByText("0.0")).not.toBeInTheDocument()
    expect(within(card).queryByText(/kg \/ wk/)).not.toBeInTheDocument()
  })

  it("nudges for a missed meal and a missing weigh-in", async () => {
    renderPage(<HomePage />)

    expect(await screen.findByText("Breakfast not logged")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Log Breakfast" })).toHaveAttribute("href", "/food")
    expect(await screen.findByText("No weigh-in today")).toBeInTheDocument()
  })

  it("adds today's weigh-in from the nudge", async () => {
    progressApi.addWeighIn.mockResolvedValue({ date: "2026-10-20", scaleKg: 79.8, trendKg: 80.3 })
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    renderPage(<HomePage />)

    await user.click(await screen.findByRole("button", { name: "Add today’s weigh-in" }))
    const dialog = await screen.findByRole("dialog", { name: "Add weigh-in" })
    expect(within(dialog).getByLabelText("Weight")).toHaveAttribute("placeholder", "80")
    await user.type(within(dialog).getByLabelText("Weight"), "79.8")
    await user.click(within(dialog).getByRole("button", { name: "Save weigh-in" }))

    await waitFor(() => expect(progressApi.addWeighIn).toHaveBeenCalledWith({ date: "2026-10-20", weightKg: 79.8 }))
    expect(toast.success).toHaveBeenCalledWith("Weigh-in saved", { description: "79.8 kg added to your trend." })
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("rejects an implausible weight", async () => {
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    renderPage(<HomePage />)

    await user.click(await screen.findByRole("button", { name: "Add today’s weigh-in" }))
    const dialog = await screen.findByRole("dialog", { name: "Add weigh-in" })
    await user.type(within(dialog).getByLabelText("Weight"), "8")
    await user.click(within(dialog).getByRole("button", { name: "Save weigh-in" }))

    expect(await within(dialog).findByText("That looks too low")).toBeInTheDocument()
    expect(progressApi.addWeighIn).not.toHaveBeenCalled()
  })

  it("shows a waiting check-in until it's put off", async () => {
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    renderPage(<HomePage />)

    expect(await screen.findByText(/has 1 proposed change\./)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Review changes" })).toHaveAttribute("href", "/coach")
    await user.click(screen.getByRole("button", { name: "Later" }))
    expect(screen.queryByText("Weekly check-in ready")).not.toBeInTheDocument()
  })

  it("starts today's planned workout", async () => {
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    renderPage(<HomePage />)

    await screen.findByText("Push day")
    await user.click(screen.getAllByRole("button", { name: "Start workout" })[0])
    expect(getActiveWorkout()?.session.name).toBe("Push day")
  })

  it("says when it's a rest day", async () => {
    workoutApi.getToday.mockResolvedValue(null)
    renderPage(<HomePage />)
    expect(await screen.findByText("Rest day — no session planned.")).toBeInTheDocument()
  })

  it("shows each card's own error with a retry", async () => {
    foodApi.getFoodLog.mockRejectedValue(new Error("down"))
    progressApi.getProgress.mockRejectedValue(new Error("down"))
    progressApi.getDailyCalories.mockRejectedValue(new Error("down"))
    workoutApi.getToday.mockRejectedValue(new Error("down"))
    renderPage(<HomePage />)

    expect(await screen.findByText("Couldn’t load today’s nutrition")).toBeInTheDocument()
    expect(await screen.findByText("Couldn’t load your weight trend")).toBeInTheDocument()
    expect(await screen.findByText("Couldn’t load recent calories")).toBeInTheDocument()
    expect(await screen.findByText("Couldn’t load today’s workout")).toBeInTheDocument()
  })
})
