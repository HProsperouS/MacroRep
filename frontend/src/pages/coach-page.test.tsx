import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
import { MemoryRouter } from "react-router-dom"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { nutritionProposal } from "@/components/coach/proposal-fixtures"
import { appliedDescription } from "@/lib/coach-messages"
import CoachPage from "@/pages/coach-page"
import { renderWithQuery } from "@/test/render"
import type { CheckIn } from "@/types/coach"

const api = vi.hoisted(() => ({
  getCurrentCheckIn: vi.fn(),
  startCheckIn: vi.fn(),
  decideProposal: vi.fn(),
  askCoach: vi.fn(),
  listMessages: vi.fn(),
}))
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
  for (const mock of Object.values(api)) mock.mockReset()
  api.listMessages.mockResolvedValue([])
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

describe("CoachPage decisions", () => {
  const training = nutritionProposal({ id: "p2", kind: "training", headline: "Add a bench set" })

  it("applies a proposal before the server answers", async () => {
    let answer!: () => void
    api.getCurrentCheckIn.mockResolvedValueOnce(checkIn()).mockResolvedValue(checkIn({ proposals: [nutritionProposal({ status: "applied" })] }))
    api.decideProposal.mockReturnValue(new Promise((resolve) => (answer = () => resolve(nutritionProposal({ status: "applied" })))))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Apply" }))

    await waitFor(() => expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument())
    expect(api.decideProposal).toHaveBeenCalledWith("c1", "p1", { decision: "apply", changes: undefined })
    answer()
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Change applied", { description: "Your daily targets are updated." }))
  })

  it("rejects a proposal", async () => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn())
    api.decideProposal.mockResolvedValue(nutritionProposal({ status: "rejected" }))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Reject" }))
    await waitFor(() => expect(api.decideProposal).toHaveBeenCalledWith("c1", "p1", { decision: "reject", changes: undefined }))
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Proposal rejected", { description: "Your plan stays as it is." }))
  })

  it("applies edited values", async () => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn())
    api.decideProposal.mockResolvedValue(nutritionProposal({ status: "edited" }))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Edit" }))
    const dialog = await screen.findByRole("dialog", { name: "Edit proposal" })
    await user.clear(within(dialog).getByLabelText("Daily calories"))
    await user.type(within(dialog).getByLabelText("Daily calories"), "2050")
    await user.click(within(dialog).getByRole("button", { name: "Apply edited values" }))

    await waitFor(() => expect(api.decideProposal).toHaveBeenCalledWith("c1", "p1", { decision: "apply", changes: [{ id: "calories", after: 2050 }] }))
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("puts a proposal back when the decision can't be saved", async () => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn())
    api.decideProposal.mockRejectedValue(new Error("down"))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Apply" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t save your decision", expect.anything()))
    expect(await screen.findByRole("button", { name: "Apply" })).toBeEnabled()
  })

  it("applies every pending proposal in order", async () => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn({ proposals: [nutritionProposal(), training] }))
    api.decideProposal.mockImplementation((_c, id: string) => Promise.resolve({ id, status: "applied" }))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Apply all" }))

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("All changes applied", { description: "Your daily targets and routines are updated." }))
    expect(api.decideProposal.mock.calls.map((call) => call[1])).toEqual(["p1", "p2"])
  })

  it("says when applying everything stopped part way", async () => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn({ proposals: [nutritionProposal(), training] }))
    api.decideProposal.mockResolvedValueOnce({ id: "p1", status: "applied" }).mockRejectedValueOnce(new Error("down"))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Apply all" }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Some changes weren’t applied", expect.anything()))
  })

  it("offers to start the first check-in", async () => {
    api.getCurrentCheckIn.mockResolvedValue(null)
    api.startCheckIn.mockResolvedValue(running)
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText("No check-in yet")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Start check-in" }))
    expect(await screen.findByText(/This page updates by itself/)).toBeInTheDocument()
  })

  it("says when there have been too many check-ins today", async () => {
    api.getCurrentCheckIn.mockResolvedValue(null)
    const detail = "That's a lot of check-ins for today. Try again in 24 hours."
    api.startCheckIn.mockRejectedValue(new AxiosError("429", "ERR_BAD_REQUEST", undefined, undefined, { status: 429, data: { detail } } as never))
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Start check-in" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t start a check-in", { description: detail }))
    expect(screen.getByText("No check-in yet")).toBeInTheDocument()
  })

  it("keeps one idempotency key across retries of a failed start", async () => {
    api.getCurrentCheckIn.mockResolvedValue(null)
    api.startCheckIn.mockRejectedValueOnce(new Error("timeout")).mockResolvedValue(running)
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Start check-in" }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t start a check-in", expect.anything()))
    await user.click(screen.getByRole("button", { name: "Start check-in" }))

    await screen.findByText(/This page updates by itself/)
    const [first, second] = api.startCheckIn.mock.calls.map((call) => call[0])
    expect(second).toBe(first)
  })
})

describe("CoachChat", () => {
  beforeEach(() => {
    api.getCurrentCheckIn.mockResolvedValue(checkIn({ suggestedQuestions: ["Why more calories?"] }))
  })

  it("shows the conversation so far", async () => {
    api.listMessages.mockResolvedValue([
      { id: "m1", role: "user", text: "Why fewer calories?" },
      { id: "m2", role: "coach", text: "Your weight held steady for a week." },
    ])
    renderPage()

    const conversation = await screen.findByRole("list", { name: "Conversation" })
    expect(await within(conversation).findByText("Your weight held steady for a week.")).toBeInTheDocument()
    expect(within(conversation).getByText("Why fewer calories?")).toBeInTheDocument()
    expect(api.listMessages).toHaveBeenCalledWith("c1", expect.anything())
  })

  it("asks a suggested question and shows the answer", async () => {
    api.askCoach.mockResolvedValue({ id: "m1", role: "coach", text: "Your weight dropped faster than planned." })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Why more calories?" }))

    const conversation = screen.getByRole("list", { name: "Conversation" })
    expect(within(conversation).getByText("Why more calories?")).toBeInTheDocument()
    expect(await within(conversation).findByText("Your weight dropped faster than planned.")).toBeInTheDocument()
    expect(api.askCoach).toHaveBeenCalledWith("c1", "Why more calories?")
  })

  it("sends a typed question with Enter and clears the box", async () => {
    api.askCoach.mockResolvedValue({ id: "m1", role: "coach", text: "Yes." })
    const user = userEvent.setup()
    renderPage()

    const box = await screen.findByRole("textbox", { name: "Ask the coach" })
    expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled()
    await user.type(box, "  Can I eat more on leg day?{Enter}")

    expect(api.askCoach).toHaveBeenCalledWith("c1", "Can I eat more on leg day?")
    expect(box).toHaveValue("")
    expect(await screen.findByText("Yes.")).toBeInTheDocument()
  })

  it("retries a question that got no answer", async () => {
    api.askCoach.mockRejectedValueOnce(new Error("down")).mockResolvedValue({ id: "m1", role: "coach", text: "Here you go." })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Why more calories?" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong")
    await user.click(screen.getByRole("button", { name: "Retry" }))

    expect(await screen.findByText("Here you go.")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    // The question is shown once, not again for the retry.
    expect(within(screen.getByRole("list", { name: "Conversation" })).getAllByText("Why more calories?")).toHaveLength(1)
  })

  it("shows the server's reason, without a retry, when the check-in can't take questions", async () => {
    api.askCoach.mockRejectedValue(
      new AxiosError("409", "ERR_BAD_REQUEST", undefined, undefined, {
        status: 409,
        data: { detail: "Questions open once the check-in is ready." },
      } as never),
    )
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Why more calories?" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Questions open once the check-in is ready.")
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
    expect(within(screen.getByRole("list", { name: "Conversation" })).queryByText("Why more calories?")).not.toBeInTheDocument()
  })

  it("says when there have been too many questions, without a retry", async () => {
    api.askCoach.mockRejectedValue(
      new AxiosError("429", "ERR_BAD_REQUEST", undefined, undefined, {
        status: 429,
        data: { detail: "That's a lot of questions for now. Try again in 12 minutes." },
      } as never),
    )
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Why more calories?" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 12 minutes.")
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
    expect(screen.getByRole("textbox", { name: "Ask the coach" })).toHaveValue("Why more calories?")
  })

  it("shows a revised proposal on its card once the coach has revised it", async () => {
    api.getCurrentCheckIn
      .mockResolvedValueOnce(checkIn({ suggestedQuestions: ["Make the cut smaller"] }))
      .mockResolvedValue(checkIn({ suggestedQuestions: ["Make the cut smaller"], proposals: [nutritionProposal({ headline: "Adjust your daily target to 2,100 kcal" })] }))
    api.askCoach.mockResolvedValue({ id: "m1", role: "coach", text: "I've revised the proposal.", kind: "revision" })
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Make the cut smaller" }))

    expect(await screen.findByText("Proposal updated")).toBeInTheDocument()
    expect(await screen.findByText("Adjust your daily target to 2,100 kcal")).toBeInTheDocument()
  })

  it("looks again for an answer the server saved after the browser gave up", async () => {
    api.askCoach.mockRejectedValue(new AxiosError("timeout", "ECONNABORTED"))
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole("button", { name: "Why more calories?" }))

    await waitFor(() => expect(api.listMessages).toHaveBeenCalledTimes(2))
  })
})

describe("appliedDescription", () => {
  it("names only what was actually applied", () => {
    const training = nutritionProposal({ id: "t", kind: "training" })
    expect(appliedDescription([nutritionProposal()])).toBe("Your daily targets are updated.")
    expect(appliedDescription([training])).toBe("Your routines are updated.")
    expect(appliedDescription([nutritionProposal(), training])).toBe("Your daily targets and routines are updated.")
  })
})
