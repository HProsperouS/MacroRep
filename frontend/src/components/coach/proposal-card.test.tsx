import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { nutritionProposal } from "@/components/coach/proposal-fixtures"
import { ProposalCard } from "@/components/coach/proposal-card"
import type { Proposal } from "@/types/coach"

function renderCard(proposal: Proposal, busy = false) {
  const handlers = { onApply: vi.fn(), onEdit: vi.fn(), onReject: vi.fn() }
  render(<ProposalCard proposal={proposal} busy={busy} {...handlers} />)
  return { user: userEvent.setup(), ...handlers }
}

describe("ProposalCard", () => {
  it("shows the current and proposed value, the change, the evidence and the reviewer's note", () => {
    renderCard(nutritionProposal())
    const row = screen.getByRole("row", { name: /Daily calories/ })
    expect(row).toHaveTextContent("2,000")
    expect(row).toHaveTextContent("2,100")
    expect(row).toHaveTextContent("+100")
    expect(screen.getByText("Averaged 1,850 kcal against a 2,000 target")).toBeInTheDocument()
    expect(screen.getByText("Within the weekly limit.")).toBeInTheDocument()
  })

  it("lets the user apply, edit or reject a pending proposal", async () => {
    const { user, onApply, onEdit, onReject } = renderCard(nutritionProposal())
    await user.click(screen.getByRole("button", { name: "Apply" }))
    await user.click(screen.getByRole("button", { name: "Edit" }))
    await user.click(screen.getByRole("button", { name: "Reject" }))
    expect(onApply).toHaveBeenCalledOnce()
    expect(onEdit).toHaveBeenCalledOnce()
    expect(onReject).toHaveBeenCalledOnce()
  })

  it("disables the actions while a decision is being sent", () => {
    renderCard(nutritionProposal(), true)
    for (const name of ["Apply", "Edit", "Reject"]) expect(screen.getByRole("button", { name })).toBeDisabled()
  })

  it.each([
    ["applied", "Applied"],
    ["edited", "Applied with edits"],
    ["rejected", "Rejected"],
  ] as const)("shows a %s proposal as decided, with no actions", (status, badge) => {
    renderCard(nutritionProposal({ status }))
    expect(screen.getByText(badge)).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })

  it("shows no change for an unchanged value", () => {
    renderCard(nutritionProposal({ changes: [{ id: "calories", label: "Daily calories", unit: "kcal", before: 2000, after: 2000, step: 50 }] }))
    expect(screen.getByRole("row", { name: /Daily calories/ })).toHaveTextContent("—")
  })
})
