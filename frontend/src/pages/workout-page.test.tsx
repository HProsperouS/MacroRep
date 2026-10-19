import { act, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { beginWorkout, clearActiveWorkout, getActiveWorkout } from "@/lib/active-workout-store"
import WorkoutPage from "@/pages/workout-page"
import { renderWithQuery } from "@/test/render"
import type { PlannedWorkout } from "@/types/workout"

const api = vi.hoisted(() => ({ getToday: vi.fn(), finishSession: vi.fn() }))
vi.mock("@/api/workout-api", () => ({ workoutApi: api }))
// Desktop layout: the mobile drawer needs browser layout APIs jsdom lacks.
vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true }))

const plan: PlannedWorkout = {
  id: "plan-1",
  name: "Push day",
  weekLabel: "Week 1",
  estimatedMinutes: 45,
  exercises: [
    {
      id: "bench",
      name: "Bench Press",
      equipment: "Barbell",
      muscles: "Chest",
      restSeconds: 90,
      sets: [{ id: "bench-0", kind: "working", targetWeightKg: 60, targetReps: 8 }],
    },
  ],
}

function renderPage() {
  return renderWithQuery(
    <MemoryRouter>
      <WorkoutPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  clearActiveWorkout()
  api.getToday.mockResolvedValue(plan)
  api.finishSession.mockResolvedValue({ id: "w1", name: "Push day", durationSeconds: 60, setsCompleted: 1, volumeKg: 480, personalRecords: [] })
})

describe("WorkoutPage pausing", () => {
  it("pauses to a stopped screen and resumes to the same sets", async () => {
    const user = userEvent.setup()
    act(() => beginWorkout(plan))
    renderPage()

    await user.click(screen.getByRole("button", { name: "Complete Bench Press set 1" }))
    await user.click(screen.getByRole("button", { name: "Pause" }))

    expect(screen.getByText("Workout paused")).toBeInTheDocument()
    expect(getActiveWorkout()?.pausedAt).not.toBeNull()
    expect(screen.queryByRole("button", { name: "Finish workout" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Pause" })).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Resume" }))

    expect(screen.queryByText("Workout paused")).not.toBeInTheDocument()
    expect(getActiveWorkout()?.pausedAt).toBeNull()
    expect(screen.getByRole("button", { name: "Mark Bench Press set 1 as not done" })).toBeInTheDocument()
  })

  it("saves the training time without the paused time", async () => {
    vi.useFakeTimers({ toFake: ["Date"] })
    vi.setSystemTime(new Date("2026-10-19T10:00:00Z"))
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    act(() => beginWorkout(plan))
    renderPage()

    await user.click(screen.getByRole("button", { name: "Complete Bench Press set 1" }))
    vi.setSystemTime(new Date("2026-10-19T10:10:00Z"))
    await user.click(screen.getByRole("button", { name: "Pause" }))
    vi.setSystemTime(new Date("2026-10-19T10:40:00Z")) // a 30 minute break
    await user.click(screen.getByRole("button", { name: "Resume" }))
    vi.setSystemTime(new Date("2026-10-19T10:45:00Z"))
    await user.click(screen.getByRole("button", { name: "Finish workout" }))

    await vi.waitFor(() => expect(api.finishSession).toHaveBeenCalledOnce())
    const sent = api.finishSession.mock.calls[0][0]
    // The real start is kept (it decides the workout's date); the finish is pulled earlier by the break.
    expect(sent.startedAt).toBe("2026-10-19T10:00:00.000Z")
    // 10 min before the break + 5 min after = 15 min of training.
    expect(Date.parse(sent.finishedAt) - Date.parse(sent.startedAt)).toBe(15 * 60_000)
    vi.useRealTimers()
  })

  it("keeps a paused workout paused after a reload", async () => {
    act(() => beginWorkout(plan))
    const user = userEvent.setup()
    const view = renderPage()
    await user.click(screen.getByRole("button", { name: "Pause" }))
    view.unmount()

    renderPage()
    expect(screen.getByText("Workout paused")).toBeInTheDocument()
  })
})
