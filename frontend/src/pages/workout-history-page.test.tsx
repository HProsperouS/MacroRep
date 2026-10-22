import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
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
    expect(api.listSessions).toHaveBeenLastCalledWith(HISTORY_PAGE_SIZE, HISTORY_PAGE_SIZE, expect.anything())
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
})
