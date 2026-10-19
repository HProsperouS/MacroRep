import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import WorkoutPlanPage from "@/pages/workout-plan-page"
import { renderWithQuery } from "@/test/render"
import { routine } from "@/test/routines"
import type { Routine, WeekPlanDay } from "@/types/workout"

const api = vi.hoisted(() => ({
  listRoutines: vi.fn(),
  getWeekPlan: vi.fn(),
  assignDay: vi.fn(),
  deletePlanDay: vi.fn(),
  createRoutine: vi.fn(),
  updateRoutine: vi.fn(),
  deleteRoutine: vi.fn(),
  searchExercises: vi.fn().mockResolvedValue([]),
}))
vi.mock("@/api/workout-api", () => ({ workoutApi: api }))
vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true }))

const push = routine("r-push", "Push", [0, 4])
const pull = routine("r-pull", "Pull", [2])

function weekFor(routines: Routine[]): WeekPlanDay[] {
  return Array.from({ length: 7 }, (_, dayOfWeek) => ({ dayOfWeek, plan: routines.find((r) => r.scheduledDays.includes(dayOfWeek)) ?? null }))
}

function renderPage() {
  return renderWithQuery(
    <MemoryRouter>
      <WorkoutPlanPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  api.listRoutines.mockResolvedValue([push, pull])
  api.getWeekPlan.mockResolvedValue(weekFor([push, pull]))
  api.assignDay.mockResolvedValue(undefined)
  api.deletePlanDay.mockResolvedValue(undefined)
})

describe("WorkoutPlanPage", () => {
  it("lists routines with the days they're scheduled on", async () => {
    renderPage()
    expect(await screen.findByText("1 exercise · Mon, Fri")).toBeInTheDocument()
    expect(screen.getByText("1 exercise · Wed")).toBeInTheDocument()
  })

  it("shows each weekday's routine, or a rest day", async () => {
    renderPage()
    expect(await screen.findByLabelText("Monday")).toHaveValue("r-push")
    expect(screen.getByLabelText("Tuesday")).toHaveValue("")
    expect(screen.getByLabelText("Wednesday")).toHaveValue("r-pull")
    expect(screen.getByLabelText("Friday")).toHaveValue("r-push")
  })

  it("schedules the same routine on another day", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.selectOptions(await screen.findByLabelText("Tuesday"), "r-push")
    await waitFor(() => expect(api.assignDay).toHaveBeenCalledWith(1, "r-push"))
  })

  it("turns a day back into a rest day without deleting the routine", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.selectOptions(await screen.findByLabelText("Wednesday"), "")
    await waitFor(() => expect(api.deletePlanDay).toHaveBeenCalledWith(2))
    expect(api.deleteRoutine).not.toHaveBeenCalled()
  })

  it("creates a routine", async () => {
    api.createRoutine.mockResolvedValue(push)
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "New routine" }))

    expect(screen.getByRole("heading", { name: "New routine" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save routine" })).toBeDisabled()
  })

  it("edits a routine and returns to the lists", async () => {
    api.updateRoutine.mockResolvedValue(push)
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit Push" }))

    const name = screen.getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Push A")
    await user.click(screen.getByRole("button", { name: "Save routine" }))

    await waitFor(() => expect(api.updateRoutine).toHaveBeenCalledOnce())
    expect(api.updateRoutine.mock.calls[0][0]).toBe("r-push")
    expect(api.updateRoutine.mock.calls[0][1].name).toBe("Push A")
    expect(await screen.findByText("Week schedule")).toBeInTheDocument()
  })

  it("deletes a routine after confirming", async () => {
    api.deleteRoutine.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Edit Push" }))
    await user.click(screen.getByRole("button", { name: "Delete routine" }))
    const dialog = await screen.findByRole("dialog", { name: "Delete this routine?" })
    await user.click(dialog.querySelector("button:last-of-type")!)

    await waitFor(() => expect(api.deleteRoutine).toHaveBeenCalledWith("r-push"))
  })

  it("explains when there are no routines yet", async () => {
    api.listRoutines.mockResolvedValue([])
    api.getWeekPlan.mockResolvedValue(weekFor([]))
    renderPage()
    expect(await screen.findByText(/No routines yet/)).toBeInTheDocument()
    expect(screen.getByLabelText("Monday")).toHaveValue("")
  })
})
