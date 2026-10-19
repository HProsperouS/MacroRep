import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { HistoryRow } from "@/components/workout/history-row"
import { renderWithQuery } from "@/test/render"
import type { WorkoutDetail, WorkoutHistoryItem } from "@/types/workout"

const api = vi.hoisted(() => ({
  getSession: vi.fn(),
  updateSession: vi.fn(),
  deleteSession: vi.fn(),
}))
vi.mock("@/api/workout-api", () => ({ workoutApi: api }))
// A real dialog rather than the mobile drawer, which needs browser layout APIs jsdom lacks.
vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true }))

const workout: WorkoutHistoryItem = {
  id: "w1",
  name: "Leg day",
  startedAt: "2026-10-19T10:00:00Z",
  durationSeconds: 1800,
  exerciseCount: 1,
  setsCompleted: 3,
  volumeKg: 740,
}

const detail: WorkoutDetail = {
  ...workout,
  exercises: [
    {
      exerciseId: "squat",
      name: "Squat",
      sets: [
        { kind: "warmup", weightKg: 40, reps: 10, rpe: null },
        { kind: "working", weightKg: 100, reps: 5, rpe: 8 },
        { kind: "drop", weightKg: 60, reps: 8, rpe: null },
      ],
    },
  ],
}

async function openRow() {
  const user = userEvent.setup()
  const view = renderWithQuery(
    <ul>
      <HistoryRow workout={workout} />
    </ul>,
  )
  await user.click(screen.getByRole("button", { name: /Leg day/ }))
  await screen.findByText("Squat")
  return { user, ...view }
}

beforeEach(() => {
  api.getSession.mockResolvedValue(detail)
})

describe("HistoryRow", () => {
  it("labels each set by its type", async () => {
    await openRow()
    const squat = screen.getByRole("heading", { name: "Squat" }).closest("section")!
    expect(within(squat).getAllByRole("listitem").map((item) => item.textContent)).toEqual(["Warm-up40 kg × 10", "Set 1100 kg × 5RPE 8", "Drop set60 kg × 8"])
  })

  it("saves a corrected set", async () => {
    api.updateSession.mockResolvedValue(detail)
    const { user } = await openRow()

    await user.click(screen.getByRole("button", { name: "Edit" }))
    const weight = screen.getByLabelText("Squat Set 1 weight in kg")
    await user.clear(weight)
    await user.type(weight, "102.5")
    await user.selectOptions(screen.getByLabelText("Squat Drop set type"), "failure")
    await user.click(screen.getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(api.updateSession).toHaveBeenCalledOnce())
    expect(api.updateSession).toHaveBeenCalledWith("w1", {
      name: "Leg day",
      exercises: [
        {
          exerciseId: "squat",
          name: "Squat",
          sets: [
            { kind: "warmup", weightKg: 40, reps: 10, rpe: undefined },
            { kind: "working", weightKg: 102.5, reps: 5, rpe: 8 },
            { kind: "failure", weightKg: 60, reps: 8, rpe: undefined },
          ],
        },
      ],
    })
    // Back to the read-only view once saved.
    await screen.findByRole("button", { name: "Edit" })
  })

  it("removes a set from the workout", async () => {
    api.updateSession.mockResolvedValue(detail)
    const { user } = await openRow()

    await user.click(screen.getByRole("button", { name: "Edit" }))
    await user.click(screen.getByRole("button", { name: "Remove Squat Warm-up" }))
    await user.click(screen.getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(api.updateSession).toHaveBeenCalledOnce())
    const sent = api.updateSession.mock.calls[0][1]
    expect(sent.exercises[0].sets.map((set: { kind: string }) => set.kind)).toEqual(["working", "drop"])
  })

  it("won't save an invalid value", async () => {
    const { user } = await openRow()

    await user.click(screen.getByRole("button", { name: "Edit" }))
    const reps = screen.getByLabelText("Squat Set 1 reps")
    await user.clear(reps)
    await user.type(reps, "5.5")

    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled()
    expect(reps).toHaveAttribute("aria-invalid", "true")
    expect(api.updateSession).not.toHaveBeenCalled()
  })

  it("cancels an edit without saving", async () => {
    const { user } = await openRow()
    await user.click(screen.getByRole("button", { name: "Edit" }))
    await user.type(screen.getByLabelText("Workout name"), " 2")
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    expect(api.updateSession).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument()
  })

  it("can't edit a workout whose exercise left the catalog", async () => {
    api.getSession.mockResolvedValue({ ...detail, exercises: [{ ...detail.exercises[0], exerciseId: null }] })
    await openRow()
    expect(screen.getByRole("button", { name: "Edit" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled()
  })

  it("deletes only after confirming", async () => {
    api.deleteSession.mockResolvedValue(undefined)
    const { user } = await openRow()

    await user.click(screen.getByRole("button", { name: "Delete" }))
    const dialog = await screen.findByRole("dialog", { name: "Delete this workout?" })
    expect(api.deleteSession).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole("button", { name: "Delete workout" }))
    await waitFor(() => expect(api.deleteSession).toHaveBeenCalledWith("w1"))
  })

  it("keeps the workout when the delete is cancelled", async () => {
    const { user } = await openRow()
    await user.click(screen.getByRole("button", { name: "Delete" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }))

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
    expect(api.deleteSession).not.toHaveBeenCalled()
  })
})
