import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { StartWorkout } from "@/components/workout/start-workout"
import { routine } from "@/test/routines"
import type { Routine } from "@/types/workout"

function renderStart(routines?: Routine[], plan = routine("r-push", "Push", [0])) {
  const handlers = { onRetryPlan: vi.fn(), onStartPlan: vi.fn(), onStartEmpty: vi.fn(), onStartRoutine: vi.fn() }
  render(<StartWorkout plan={plan} planPending={false} planError={null} routines={routines} {...handlers} />)
  return { user: userEvent.setup(), ...handlers }
}

describe("StartWorkout", () => {
  it("lets the user start any routine, not just today's", async () => {
    const pull = routine("r-pull", "Pull", [2])
    const { user, onStartRoutine } = renderStart([routine("r-push", "Push", [0]), pull])

    expect(screen.getByText(/Mon/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Start Pull" }))
    expect(onStartRoutine).toHaveBeenCalledWith(pull)
  })

  it("still starts today's plan and an empty workout", async () => {
    const { user, onStartPlan, onStartEmpty } = renderStart([])
    await user.click(screen.getByRole("button", { name: "Start planned workout" }))
    await user.click(screen.getByRole("button", { name: "Start empty workout" }))
    expect(onStartPlan).toHaveBeenCalledOnce()
    expect(onStartEmpty).toHaveBeenCalledOnce()
  })

  it("hides the routines list when there are none or they haven't loaded", () => {
    renderStart([])
    expect(screen.queryByText("Your routines")).not.toBeInTheDocument()
    cleanup()
    renderStart(undefined)
    expect(screen.queryByText("Your routines")).not.toBeInTheDocument()
  })
})
