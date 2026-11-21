import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ChangeEmail } from "@/components/profile/change-email"
import { renderWithQuery } from "@/test/render"

const authApi = vi.hoisted(() => ({ requestEmailChange: vi.fn(), confirmEmailChange: vi.fn(), cancelEmailChange: vi.fn() }))
vi.mock("@/api/auth-api", () => ({ authApi }))

const refused = (status: number, detail: string) => new AxiosError(String(status), "ERR_BAD_REQUEST", undefined, undefined, { status, data: { detail } } as never)

// Inside a form, as on the profile page: submitting the overlay mustn't submit that one too.
const outerSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault())

function renderChangeEmail() {
  return renderWithQuery(
    <form onSubmit={outerSubmit}>
      <ChangeEmail currentEmail="alex@example.com" />
    </form>,
  )
}

async function sendCode(user: ReturnType<typeof userEvent.setup>, email = "New@Example.com", password = "long-enough-pw") {
  await user.click(screen.getByRole("button", { name: "Change" }))
  await user.type(await screen.findByLabelText("New email"), email)
  await user.type(screen.getByLabelText("Current password"), password)
  await user.click(screen.getByRole("button", { name: "Send code" }))
}

beforeEach(() => {
  vi.clearAllMocks()
  authApi.requestEmailChange.mockResolvedValue(undefined)
  authApi.confirmEmailChange.mockResolvedValue({ id: "u1", name: "Alex", email: "new@example.com" })
  authApi.cancelEmailChange.mockResolvedValue(undefined)
})

describe("ChangeEmail", () => {
  it("sends a code to the new email, then confirms it", async () => {
    const success = vi.spyOn(toast, "success")
    const user = userEvent.setup()
    renderChangeEmail()

    await sendCode(user)
    expect(authApi.requestEmailChange).toHaveBeenCalledWith({ newEmail: "New@Example.com", password: "long-enough-pw" })
    expect(await screen.findByText("Enter the code we sent to new@example.com.")).toBeInTheDocument()

    await user.type(screen.getByLabelText("Code"), "123456")
    await user.click(screen.getByRole("button", { name: "Confirm" }))

    await waitFor(() => expect(authApi.confirmEmailChange).toHaveBeenCalledWith({ code: "123456" }))
    await waitFor(() => expect(success).toHaveBeenCalledWith("Email changed", expect.anything()))
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument()
    expect(authApi.cancelEmailChange).not.toHaveBeenCalled()
    expect(outerSubmit).not.toHaveBeenCalled()
  })

  it("checks the code's format before sending it", async () => {
    const user = userEvent.setup()
    renderChangeEmail()
    await sendCode(user)

    await user.type(await screen.findByLabelText("Code"), "12ab")
    await user.click(screen.getByRole("button", { name: "Confirm" }))

    expect(await screen.findByText("Enter the 6-digit code")).toBeInTheDocument()
    expect(authApi.confirmEmailChange).not.toHaveBeenCalled()
  })

  it("shows a wrong password and a taken email on their fields", async () => {
    authApi.requestEmailChange.mockRejectedValueOnce(refused(403, "Incorrect password"))
    authApi.requestEmailChange.mockRejectedValueOnce(refused(409, "That email is already registered"))
    const user = userEvent.setup()
    renderChangeEmail()

    await sendCode(user)
    expect(await screen.findByText("Incorrect password")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Send code" }))
    expect(await screen.findByText("That email is already registered")).toBeInTheDocument()
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument()
  })

  it("shows a wrong code on the code field", async () => {
    authApi.confirmEmailChange.mockRejectedValueOnce(refused(422, "That code isn't right"))
    const user = userEvent.setup()
    renderChangeEmail()
    await sendCode(user)

    await user.type(await screen.findByLabelText("Code"), "000000")
    await user.click(screen.getByRole("button", { name: "Confirm" }))

    expect(await screen.findByText("That code isn't right")).toBeInTheDocument()
    expect(screen.getByLabelText("Code")).toBeInTheDocument()
  })

  it("drops the sent code when cancelled", async () => {
    const user = userEvent.setup()
    renderChangeEmail()
    await sendCode(user)

    await screen.findByLabelText("Code")
    await user.click(screen.getByRole("button", { name: "Cancel" }))

    await waitFor(() => expect(authApi.cancelEmailChange).toHaveBeenCalled())
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument()
  })

  it("cancels before a code is sent without calling the API", async () => {
    const user = userEvent.setup()
    renderChangeEmail()

    await user.click(screen.getByRole("button", { name: "Change" }))
    await user.click(await screen.findByRole("button", { name: "Cancel" }))

    expect(authApi.cancelEmailChange).not.toHaveBeenCalled()
    expect(authApi.requestEmailChange).not.toHaveBeenCalled()
  })
})
