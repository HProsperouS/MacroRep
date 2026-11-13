import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { format, subDays } from "date-fns"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { HISTORY_PAGE_SIZE } from "@/hooks/use-workout"
import WorkoutHistoryPage from "@/pages/workout-history-page"
import { renderPage } from "@/test/render"
import type { WorkoutHistoryItem } from "@/types/workout"

const api = vi.hoisted(() => ({ listSessions: vi.fn() }))
vi.mock("@/api/workout-api", () => ({ workoutApi: api }))

function workouts(from: number, count: number): WorkoutHistoryItem[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `w${from + index}`,
    name: `Workout ${from + index}`,
    startedAt: "2026-10-19T10:00:00Z",
    durationSeconds: 1800,
    exerciseCount: 1,
    setsCompleted: 3,
    volumeKg: 1000,
  }))
}

beforeEach(() => {
  api.listSessions.mockImplementation((offset: number) => Promise.resolve(workouts(offset, offset === 0 ? HISTORY_PAGE_SIZE : 5)))
})

describe("WorkoutHistoryPage", () => {
  it("loads more until a short page shows the end", async () => {
    const user = userEvent.setup()
    renderPage(<WorkoutHistoryPage />)

    expect(await screen.findByText(`Workout ${HISTORY_PAGE_SIZE - 1}`)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Load more" }))

    expect(await screen.findByText(`Workout ${HISTORY_PAGE_SIZE + 4}`)).toBeInTheDocument()
    expect(api.listSessions).toHaveBeenLastCalledWith(HISTORY_PAGE_SIZE, HISTORY_PAGE_SIZE, {}, expect.anything())
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument()
  })

  it("offers a retry when the next page fails, keeping what's loaded", async () => {
    api.listSessions.mockResolvedValueOnce(workouts(0, HISTORY_PAGE_SIZE)).mockRejectedValueOnce(new Error("down"))
    const user = userEvent.setup()
    renderPage(<WorkoutHistoryPage />)

    await user.click(await screen.findByRole("button", { name: "Load more" }))

    expect(await screen.findByText("Couldn’t load more workouts")).toBeInTheDocument()
    expect(screen.getByText("Workout 0")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText(`Workout ${HISTORY_PAGE_SIZE + 4}`)).toBeInTheDocument()
  })

  it("says when nothing has been logged", async () => {
    api.listSessions.mockResolvedValue([])
    renderPage(<WorkoutHistoryPage />)
    expect(await screen.findByText("No workouts yet")).toBeInTheDocument()
  })

  it("offers a retry when the history can't be loaded", async () => {
    api.listSessions.mockRejectedValueOnce(new Error("down"))
    const user = userEvent.setup()
    renderPage(<WorkoutHistoryPage />)

    expect(await screen.findByText("Couldn’t load your workouts")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Retry" }))
    await waitFor(() => expect(screen.getByText("Workout 0")).toBeInTheDocument())
  })

  it("filters to today, the past week and the past month", async () => {
    const user = userEvent.setup()
    const day = (daysAgo: number) => format(subDays(new Date(), daysAgo), "yyyy-MM-dd")
    renderPage(<WorkoutHistoryPage />)
    await screen.findByText("Workout 0")

    await user.click(screen.getByRole("radio", { name: "Today" }))
    await waitFor(() => expect(api.listSessions).toHaveBeenLastCalledWith(0, HISTORY_PAGE_SIZE, { from: day(0), to: day(0) }, expect.anything()))
    await user.click(screen.getByRole("radio", { name: /week/i }))
    await waitFor(() => expect(api.listSessions).toHaveBeenLastCalledWith(0, HISTORY_PAGE_SIZE, { from: day(6), to: day(0) }, expect.anything()))
    await user.click(screen.getByRole("radio", { name: /month/i }))
    await waitFor(() => expect(api.listSessions).toHaveBeenLastCalledWith(0, HISTORY_PAGE_SIZE, { from: day(29), to: day(0) }, expect.anything()))
  })

  it("starts from the range in the URL and asks for a custom one", async () => {
    renderPage(<WorkoutHistoryPage />, "/?range=custom&from=2026-10-01&to=2026-10-15")
    expect(await screen.findByLabelText("From")).toHaveValue("2026-10-01")
    expect(screen.getByLabelText("To")).toHaveValue("2026-10-15")
    await waitFor(() => expect(api.listSessions).toHaveBeenCalledWith(0, HISTORY_PAGE_SIZE, { from: "2026-10-01", to: "2026-10-15" }, expect.anything()))
  })

  it("won't ask for a range that ends before it starts", async () => {
    renderPage(<WorkoutHistoryPage />, "/?range=custom&from=2026-10-15&to=2026-10-01")
    expect(await screen.findByRole("alert")).toHaveTextContent("The start date is after the end date.")
    expect(api.listSessions).not.toHaveBeenCalled()
  })

  it("says when a period has no workouts and offers to show all", async () => {
    api.listSessions.mockResolvedValue([])
    const user = userEvent.setup()
    renderPage(<WorkoutHistoryPage />, "/?range=today")
    expect(await screen.findByText("No workouts in this period")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Show all" }))
    await waitFor(() => expect(api.listSessions).toHaveBeenLastCalledWith(0, HISTORY_PAGE_SIZE, {}, expect.anything()))
  })
})
