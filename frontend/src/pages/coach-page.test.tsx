import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { nutritionProposal } from "@/components/coach/proposal-fixtures"
import CoachPage from "@/pages/coach-page"
import { renderWithQuery } from "@/test/render"
import type { CheckIn } from "@/types/coach"

const api = vi.hoisted(() => ({ getCurrentCheckIn: vi.fn(), startCheckIn: vi.fn(), decideProposal: vi.fn(), askCoach: vi.fn() }))
vi.mock("@/api/coach-api", () => ({ coachApi: api }))
vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true }))

function checkIn(overrides: Partial<CheckIn> = {}): CheckIn {
  return {
    id: "c1",
    weekLabel: "Week 2",
    rangeLabel: "2026-10-13 – 2026-10-19",
    status: "needs-review",
    failureReason: null,
    summary: "Averaged 2,000 kcal/day.",
    stats: [],
    pipeline: [{ id: "gather", title: "Gather week's data", detail: "Food log, workouts, weigh-ins.", status: "done" }],
    proposals: [nutritionProposal()],
    suggestedQuestions: [],
    ...overrides,
  }
}

const running = checkIn({
  status: "running",
  summary: "Reviewing your week…",
  proposals: [],
  pipeline: [
    { id: "gather", title: "Gather week's data", detail: "Food log, workouts, weigh-ins.", status: "done" },
    { id: "propose", title: "Draft proposals", detail: "Reviewing your week…", status: "running" },
  ],
})

function renderPage() {
  return renderWithQuery(
    <MemoryRouter>
      <CoachPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  api.getCurrentCheckIn.mockReset()
})

describe("CoachPage", () => {
  it("shows a running check-in and updates by itself when it's ready", async () => {
    api.getCurrentCheckIn.mockResolvedValueOnce(running).mockResolvedValue(checkIn())
    renderPage()

    expect(await screen.findByText(/This page updates by itself/)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Apply/ })).not.toBeInTheDocument()

    // Polled again after a couple of seconds, without the user doing anything.
    expect(await screen.findByText("Raise calories slightly", undefined, { timeout: 4_000 })).toBeInTheDocument()
    expect(api.getCurrentCheckIn).toHaveBeenCalledTimes(2)
  })

  it("refreshes the progress history once a running check-in finishes", async () => {
    api.getCurrentCheckIn.mockResolvedValueOnce(running).mockResolvedValue(checkIn())
    const { queryClient } = renderPage()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")

    await screen.findByText(/This page updates by itself/)
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["progress"] })

    await screen.findByText("Raise calories slightly", undefined, { timeout: 4_000 })
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["progress"] }))
  })

  it("stops polling once the check-in is ready", async () => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn())
    renderPage()
    await screen.findByText("Raise calories slightly")
    await new Promise((resolve) => setTimeout(resolve, 2_500))
    expect(api.getCurrentCheckIn).toHaveBeenCalledTimes(1)
  })

  it("explains a failed check-in and offers to try again", async () => {
    api.getCurrentCheckIn.mockResolvedValue(
      checkIn({ status: "failed", proposals: [], failureReason: "Something went wrong while preparing this check-in. Nothing was changed." }),
    )
    api.startCheckIn.mockResolvedValue(running)
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText("This check-in couldn’t be prepared")).toBeInTheDocument()
    expect(screen.getByText(/Nothing was changed/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Try again" }))
    await waitFor(() => expect(api.startCheckIn).toHaveBeenCalledOnce())
    expect(await screen.findByText(/This page updates by itself/)).toBeInTheDocument()
  })
})
