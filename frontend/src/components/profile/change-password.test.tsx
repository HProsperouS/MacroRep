import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ChangePassword } from "@/components/profile/change-password"
import { getAccessToken, setAccessToken } from "@/lib/auth"
import { renderWithQuery } from "@/test/render"

const authApi = vi.hoisted(() => ({ changePassword: vi.fn() }))
vi.mock("@/api/auth-api", () => ({ authApi }))

const refused = (status: number, detail: string) => new AxiosError(String(status), "ERR_BAD_REQUEST", undefined, undefined, { status, data: { detail } } as never)

// Inside a form, as on the profile page: submitting the overlay mustn't submit that one too.
const outerSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault())

async function fillIn(user: ReturnType<typeof userEvent.setup>, current: string, next: string, repeat = next) {
  await user.click(screen.getByRole("button", { name: "Change" }))
  await user.type(await screen.findByLabelText("Current password"), current)
  await user.type(screen.getByLabelText("New password"), next)
  await user.type(screen.getByLabelText("New password again"), repeat)
  await user.click(screen.getByRole("button", { name: "Change password" }))
}

beforeEach(() => {
  vi.clearAllMocks()
  setAccessToken("old-token")
  authApi.changePassword.mockResolvedValue({ accessToken: "new-token" })
  renderWithQuery(
    <form onSubmit={outerSubmit}>
      <ChangePassword />
    </form>,
  )
})

describe("ChangePassword", () => {
  it("changes the password and keeps this device signed in with the new session", async () => {
    const success = vi.spyOn(toast, "success")
    const user = userEvent.setup()

    await fillIn(user, "long-enough-pw", "a-brand-new-passphrase")

    await waitFor(() => expect(authApi.changePassword).toHaveBeenCalledWith({ currentPassword: "long-enough-pw", newPassword: "a-brand-new-passphrase" }))
    await waitFor(() => expect(success).toHaveBeenCalledWith("Password changed", expect.anything()))
    expect(getAccessToken()).toBe("new-token")
    expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument()
    expect(outerSubmit).not.toHaveBeenCalled()
  })

  it("checks the new password is long enough and typed the same twice", async () => {
    const user = userEvent.setup()

    await fillIn(user, "long-enough-pw", "short", "different")

    expect(await screen.findByText("Use at least 8 characters")).toBeInTheDocument()
    expect(screen.getByText("The passwords don’t match")).toBeInTheDocument()
    expect(authApi.changePassword).not.toHaveBeenCalled()
  })

  it("shows a wrong current password and a refused new one on their fields", async () => {
    authApi.changePassword.mockRejectedValueOnce(refused(403, "Incorrect password"))
    authApi.changePassword.mockRejectedValueOnce(refused(422, "That password is too common. Pick one that's harder to guess"))
    const user = userEvent.setup()

    await fillIn(user, "wrong-password", "password123")
    expect(await screen.findByText("Incorrect password")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Change password" }))
    expect(await screen.findByText("That password is too common. Pick one that's harder to guess")).toBeInTheDocument()
    expect(getAccessToken()).toBe("old-token")
  })
})
