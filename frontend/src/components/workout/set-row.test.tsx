import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { SetRow } from "@/components/workout/set-row"
import type { SessionSet } from "@/lib/workout-session"

function renderRow(overrides: Partial<SessionSet> = {}, label = "1") {
  const handlers = { onEdit: vi.fn(), onKindChange: vi.fn(), onToggle: vi.fn() }
  const set: SessionSet = { id: "s1", kind: "working", weight: "60", reps: "8", rpe: "", done: false, ...overrides }
  render(
    <ul>
      <SetRow exerciseName="Bench Press" set={set} label={label} active={false} {...handlers} />
    </ul>,
  )
  return handlers
}

describe("SetRow", () => {
  it("reports edits to weight, reps and RPE", async () => {
    const user = userEvent.setup()
    const { onEdit } = renderRow({ weight: "", reps: "", rpe: "" })

    await user.type(screen.getByLabelText("Bench Press set 1 weight in kg"), "6")
    await user.type(screen.getByLabelText("Bench Press set 1 reps"), "8")
    await user.type(screen.getByLabelText("Bench Press set 1 RPE, 1 to 10, optional"), "9")

    expect(onEdit).toHaveBeenNthCalledWith(1, "weight", "6")
    expect(onEdit).toHaveBeenNthCalledWith(2, "reps", "8")
    expect(onEdit).toHaveBeenNthCalledWith(3, "rpe", "9")
  })

  it("completes a valid set with one tap", async () => {
    const user = userEvent.setup()
    const { onToggle } = renderRow()
    await user.click(screen.getByRole("button", { name: "Complete Bench Press set 1" }))
    expect(onToggle).toHaveBeenCalledOnce()
  })

  it.each([
    ["reps are missing", { reps: "" }],
    ["weight is missing", { weight: "" }],
    ["RPE is out of range", { rpe: "11" }],
  ])("can't be completed while %s", async (_label, overrides) => {
    const user = userEvent.setup()
    const { onToggle } = renderRow(overrides)
    const button = screen.getByRole("button", { name: "Complete Bench Press set 1" })
    expect(button).toBeDisabled()
    await user.click(button)
    expect(onToggle).not.toHaveBeenCalled()
  })

  it("locks a completed set's inputs and offers to undo it", async () => {
    const user = userEvent.setup()
    const { onToggle } = renderRow({ done: true })
    expect(screen.getByLabelText("Bench Press set 1 weight in kg")).toBeDisabled()
    expect(screen.getByRole("button", { name: /type: Working/ })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Mark Bench Press set 1 as not done" }))
    expect(onToggle).toHaveBeenCalledOnce()
  })

  it("changes the set type from its label", async () => {
    const user = userEvent.setup()
    const { onKindChange } = renderRow()

    // Opened from the keyboard: jsdom has no PointerEvent for Radix's pointer-down handler.
    screen.getByRole("button", { name: "Bench Press set 1 type: Working. Change type" }).focus()
    await user.keyboard("{Enter}")
    expect(screen.getAllByRole("menuitemradio").map((item) => item.textContent)).toEqual(["Warm-up", "Working", "Failure", "Drop set"])
    await user.click(screen.getByRole("menuitemradio", { name: "Failure" }))

    expect(onKindChange).toHaveBeenCalledWith("failure")
  })

  it("shows the previous result", () => {
    renderRow({ previous: { weightKg: 57.5, reps: 8, rpe: 8 } })
    expect(screen.getByText("57.5 × 8 @8")).toBeInTheDocument()
  })
})
