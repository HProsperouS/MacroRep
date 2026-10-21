import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { nutritionProposal } from "@/components/coach/proposal-fixtures"
import { EditProposalForm } from "@/components/coach/edit-proposal-form"

function renderForm() {
  const handlers = { onSubmit: vi.fn(), onCancel: vi.fn() }
  render(<EditProposalForm proposal={nutritionProposal()} submitting={false} {...handlers} />)
  return { user: userEvent.setup(), ...handlers }
}

async function typeValue(user: ReturnType<typeof userEvent.setup>, value: string) {
  const field = screen.getByLabelText("Daily calories")
  await user.clear(field)
  if (value) await user.type(field, value)
}

describe("EditProposalForm", () => {
  it("starts from the proposed values and applies them unchanged", async () => {
    const { user, onSubmit } = renderForm()
    expect(screen.getByLabelText("Daily calories")).toHaveValue("2100")
    await user.click(screen.getByRole("button", { name: "Apply edited values" }))
    expect(onSubmit).toHaveBeenCalledWith([{ id: "calories", after: 2100 }])
  })

  it("applies an edited value", async () => {
    const { user, onSubmit } = renderForm()
    await typeValue(user, "2150")
    await user.click(screen.getByRole("button", { name: "Apply edited values" }))
    expect(onSubmit).toHaveBeenCalledWith([{ id: "calories", after: 2150 }])
  })

  it.each([
    ["is blank", "", "Enter a number"],
    ["isn't a number", "lots", "Enter a number"],
    ["is below the lowest target the server applies", "0", "Must be at least 1,000"],
    ["moves more than 25% from the current value", "2600", "Stay within 25% of 2,000"],
    ["drops more than 25% below the current value", "1400", "Stay within 25% of 2,000"],
  ])("refuses a value that %s", async (_label, value, message) => {
    const { user, onSubmit } = renderForm()
    await typeValue(user, value)
    expect(screen.queryByText(message)).not.toBeInTheDocument() // only shown once the user tries to apply
    await user.click(screen.getByRole("button", { name: "Apply edited values" }))
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("accepts the edge of the allowed range", async () => {
    const { user, onSubmit } = renderForm()
    await typeValue(user, "2500")
    await user.click(screen.getByRole("button", { name: "Apply edited values" }))
    expect(onSubmit).toHaveBeenCalledWith([{ id: "calories", after: 2500 }])
  })

  it("cancels", async () => {
    const { user, onCancel } = renderForm()
    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})
