import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, useLocation } from "react-router-dom"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import ProgressPage from "@/pages/progress-page"
import { progressResponse } from "@/test/progress"
import { renderWithQuery } from "@/test/render"
import type { WeighIn } from "@/types/progress"

const api = vi.hoisted(() => ({
  getProgress: vi.fn(),
  listWeighIns: vi.fn(),
  addWeighIn: vi.fn(),
  updateWeighIn: vi.fn(),
  deleteWeighIn: vi.fn(),
}))
vi.mock("@/api/progress-api", () => ({ progressApi: api }))
vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true }))

const weighIns: WeighIn[] = [
  { id: "w2", date: "2026-10-19", weightKg: 80, trendKg: 80.5 },
  { id: "w1", date: "2026-10-18", weightKg: 80.4, trendKg: 80.6 },
]

function Search() {
  return <output aria-label="search">{useLocation().search}</output>
}

function renderPage(url = "/progress") {
  return renderWithQuery(
    <MemoryRouter initialEntries={[url]}>
      <ProgressPage />
      <Search />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  api.getProgress.mockImplementation((range: string) => Promise.resolve(progressResponse({ range: range as never })))
  api.listWeighIns.mockResolvedValue(weighIns)
})

describe("ProgressPage", () => {
  it("shows the period's stats, lifts and check-ins", async () => {
    renderPage()

    expect(await screen.findByText("21 September – 20 October")).toBeInTheDocument()
    expect(screen.getByText("−1.2 kg this period")).toBeInTheDocument()
    expect(screen.getByText("25 complete · 2 under half target")).toBeInTheDocument()
    expect(screen.getByText("−200 kcal / logged day vs target")).toBeInTheDocument()
    expect(screen.getByText("10 / 12")).toBeInTheDocument()
    expect(screen.getByText("83% of planned")).toBeInTheDocument()
    expect(screen.getByText("Last full week · +12% vs prior")).toBeInTheDocument()
    expect(screen.getByText("This week · +0.5 vs last week")).toBeInTheDocument()
    expect(screen.getByText("Average 13 t")).toBeInTheDocument()
    expect(screen.getByText("92.5")).toBeInTheDocument()
    expect(screen.getByText("Week 3 · 13 Oct")).toBeInTheDocument()
    expect(screen.getByText("Applied")).toBeInTheDocument()
    expect(await screen.findByText("2 logged")).toBeInTheDocument()
  })

  it("explains empty sections", async () => {
    api.getProgress.mockResolvedValue(
      progressResponse({
        adherencePercent: null,
        weight: { ...progressResponse().weight, points: [{ date: "2026-10-20", scaleKg: null, trendKg: 80 }], ratePerWeekKg: null },
        logging: { completeDays: 0, partialDays: 0, targetAdherencePercent: null, targetGapKcal: 0 },
        workouts: { done: 0, planned: 0, completionPercent: null },
        volume: { ...progressResponse().volume, changePercent: null },
        rpe: { thisWeekAvg: null, change: null },
        strength: [],
        checkIns: [],
      }),
    )
    api.listWeighIns.mockResolvedValue([])
    renderPage()

    // The chart's and the list's.
    await waitFor(() => expect(screen.getAllByText("No weigh-ins in this period.")).toHaveLength(2))
    expect(screen.getByText("Logged days within ±10%")).toBeInTheDocument()
    expect(screen.getByText("No plan set")).toBeInTheDocument()
    // Weigh-ins don't cover a week yet: no rate, and no verdict against the goal.
    expect(screen.getByText("Rate").parentElement).toHaveTextContent(/^Rate—Needs a week of weigh-ins$/)
    // Nothing finished yet: a dash, not 0%.
    expect(screen.getByText("Days logged").parentElement).toHaveTextContent(/^Days logged—/)
    expect(screen.getByText("No RPE logged this week yet")).toBeInTheDocument()
    expect(screen.getByText(/Log a few working sets/)).toBeInTheDocument()
    expect(screen.getByText("No check-ins in this period.")).toBeInTheDocument()
  })

  it("keeps the chosen range in the URL", async () => {
    const user = userEvent.setup()
    renderPage("/progress?range=3M")

    await screen.findByText("21 September – 20 October")
    expect(api.getProgress).toHaveBeenLastCalledWith("3M", expect.anything())
    expect(screen.getByRole("radio", { name: "3M" })).toHaveAttribute("data-state", "on")

    await user.click(screen.getByRole("radio", { name: "1Y" }))
    await waitFor(() => expect(api.getProgress).toHaveBeenLastCalledWith("1Y", expect.anything()))
    expect(screen.getByRole("status", { name: "search" })).toHaveTextContent("?range=1Y")

    await user.click(screen.getByRole("radio", { name: "1M" }))
    expect(screen.getByRole("status", { name: "search" })).toBeEmptyDOMElement()
  })

  it("lists only the latest 12 months of weigh-ins for a longer range", async () => {
    api.getProgress.mockResolvedValue(progressResponse({ range: "All", from: "2024-01-01", to: "2026-10-20" }))
    renderPage("/progress?range=All")

    expect(await screen.findByText("Latest 12 months")).toBeInTheDocument()
    expect(api.listWeighIns).toHaveBeenCalledWith("2025-10-20", "2026-10-20", expect.anything())
  })

  it("offers a retry when progress can't be loaded", async () => {
    api.getProgress.mockRejectedValueOnce(new Error("down"))
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText("Couldn’t load your progress")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("21 September – 20 October")).toBeInTheDocument()
  })
})

describe("Weigh-ins", () => {
  it("adds a weigh-in for a missed day", async () => {
    api.addWeighIn.mockResolvedValue({ date: "2026-10-15", scaleKg: 80.9, trendKg: 80.7 })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Add weigh-in" }))
    const dialog = await screen.findByRole("dialog", { name: "Add weigh-in" })
    expect(within(dialog).getByLabelText("Weight")).toHaveAttribute("placeholder", "80")
    await user.type(within(dialog).getByLabelText("Weight"), "80.9")
    await user.clear(within(dialog).getByLabelText("Day"))
    await user.type(within(dialog).getByLabelText("Day"), "2026-10-15")
    await user.click(within(dialog).getByRole("button", { name: "Save weigh-in" }))

    await waitFor(() => expect(api.addWeighIn).toHaveBeenCalledWith({ date: "2026-10-15", weightKg: 80.9 }))
    expect(toast.success).toHaveBeenCalledWith("Weigh-in saved", { description: "80.9 kg on Thu 15 Oct 2026" })
    // The trend moves with every weigh-in, so the page reloads it.
    await waitFor(() => expect(api.getProgress).toHaveBeenCalledTimes(2))
  })

  it("refuses a day in the future", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Add weigh-in" }))
    const dialog = await screen.findByRole("dialog", { name: "Add weigh-in" })
    await user.type(within(dialog).getByLabelText("Weight"), "80")
    await user.clear(within(dialog).getByLabelText("Day"))
    await user.type(within(dialog).getByLabelText("Day"), "2999-01-01")
    await user.click(within(dialog).getByRole("button", { name: "Save weigh-in" }))

    expect(await within(dialog).findByText("Pick today or an earlier day")).toBeInTheDocument()
    expect(api.addWeighIn).not.toHaveBeenCalled()
  })

  it("edits a weigh-in, sending only what changed", async () => {
    api.updateWeighIn.mockResolvedValue({ ...weighIns[0], weightKg: 79.6 })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Edit weigh-in on Mon 19 Oct 2026" }))
    const dialog = await screen.findByRole("dialog", { name: "Edit weigh-in" })
    await user.clear(within(dialog).getByLabelText("Weight"))
    await user.type(within(dialog).getByLabelText("Weight"), "79.6")
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(api.updateWeighIn).toHaveBeenCalledWith("w2", { weightKg: 79.6 }))
    expect(toast.success).toHaveBeenCalledWith("Weigh-in updated", { description: "79.6 kg on Mon 19 Oct 2026" })
  })

  it("closes an unchanged edit without a request", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Edit weigh-in on Mon 19 Oct 2026" }))
    const dialog = await screen.findByRole("dialog", { name: "Edit weigh-in" })
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(api.updateWeighIn).not.toHaveBeenCalled()
  })

  it("reports a clash when moving onto a day that has a weigh-in", async () => {
    api.updateWeighIn.mockRejectedValue(new Error("conflict"))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Edit weigh-in on Mon 19 Oct 2026" }))
    const dialog = await screen.findByRole("dialog", { name: "Edit weigh-in" })
    await user.clear(within(dialog).getByLabelText("Day"))
    await user.type(within(dialog).getByLabelText("Day"), "2026-10-18")
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t update that weigh-in", expect.anything()))
    expect(api.updateWeighIn).toHaveBeenCalledWith("w2", { date: "2026-10-18" })
    expect(screen.getByRole("dialog", { name: "Edit weigh-in" })).toBeInTheDocument()
  })

  it("deletes a weigh-in and can put it back", async () => {
    api.deleteWeighIn.mockResolvedValue(undefined)
    api.addWeighIn.mockResolvedValue({ date: "2026-10-18", scaleKg: 80.4, trendKg: 80.6 })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Delete weigh-in on Sun 18 Oct 2026" }))

    await waitFor(() => expect(api.deleteWeighIn).toHaveBeenCalledWith("w1"))
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Weigh-in deleted", expect.objectContaining({ description: "80.4 kg on Sun 18 Oct 2026" })))
    const { action } = vi.mocked(toast).mock.calls[0][1] as unknown as { action: { onClick: () => void } }
    action.onClick()
    await waitFor(() => expect(api.addWeighIn).toHaveBeenCalledWith({ date: "2026-10-18", weightKg: 80.4 }))
  })

  it("offers a retry when weigh-ins can't be loaded", async () => {
    api.listWeighIns.mockRejectedValue(new Error("down"))
    renderPage()
    expect(await screen.findByText("Couldn’t load your weigh-ins")).toBeInTheDocument()
  })
})
