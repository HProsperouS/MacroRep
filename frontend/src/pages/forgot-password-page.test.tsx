import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { clearAccessToken, getAccessToken } from "@/lib/auth"
import ForgotPasswordPage from "@/pages/forgot-password-page"
import { renderWithQuery } from "@/test/render"

const authApi = vi.hoisted(() => ({ requestPasswordReset: vi.fn(), confirmPasswordReset: vi.fn() }))
vi.mock("@/api/auth-api", () => ({ authApi }))

const refused = (status: number, detail: string) => new AxiosError(String(status), "ERR_BAD_REQUEST", undefined, undefined, { status, data: { detail } } as never)

function renderPage() {
  return renderWithQuery(
    <MemoryRouter initialEntries={["/forgot-password"]}>
      <Routes>
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/" element={<p>Home page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function askForCode(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Email"), "Alex@Example.com")
  await user.click(screen.getByRole("button", { name: "Send code" }))
  await screen.findByLabelText("Code")
}

async function reset(user: ReturnType<typeof userEvent.setup>, code: string, password: string) {
  await user.type(screen.getByLabelText("Code"), code)
  await user.type(screen.getByLabelText("New password"), password)
  await user.type(screen.getByLabelText("New password again"), password)
  await user.click(screen.getByRole("button", { name: "Reset password" }))
}

beforeEach(() => {
  vi.clearAllMocks()
  clearAccessToken()
  authApi.requestPasswordReset.mockResolvedValue(undefined)
  authApi.confirmPasswordReset.mockResolvedValue({ accessToken: "fresh" })
})

describe("ForgotPasswordPage", () => {
  it("sends a code, then resets the password and signs in", async () => {
    const user = userEvent.setup()
    renderPage()

    await askForCode(user)
    expect(authApi.requestPasswordReset).toHaveBeenCalledWith({ email: "Alex@Example.com" })
    // Worded so it doesn't say whether the email has an account.
    expect(screen.getByText(/If alex@example.com has an account, we sent it a code/)).toBeInTheDocument()

    await reset(user, "123456", "a-brand-new-passphrase")

    await waitFor(() =>
      expect(authApi.confirmPasswordReset).toHaveBeenCalledWith({ email: "alex@example.com", code: "123456", newPassword: "a-brand-new-passphrase" }),
    )
    expect(await screen.findByText("Home page")).toBeInTheDocument()
    expect(getAccessToken()).toBe("fresh")
  })

  it("shows a wrong code on the code field and a refused password on the password field", async () => {
    authApi.confirmPasswordReset.mockRejectedValueOnce(refused(422, "That code isn't right or has expired. Check it, or ask for a new one."))
    authApi.confirmPasswordReset.mockRejectedValueOnce(refused(422, "That password is too common. Pick one that's harder to guess"))
    const user = userEvent.setup()
    renderPage()
    await askForCode(user)

    await reset(user, "000000", "password123")
    expect(await screen.findByText(/That code isn't right/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Reset password" }))
    expect(await screen.findByText(/That password is too common/)).toBeInTheDocument()
    expect(getAccessToken()).toBeNull()
  })

  it("checks the code and the new password before sending them", async () => {
    const user = userEvent.setup()
    renderPage()
    await askForCode(user)

    await user.type(screen.getByLabelText("Code"), "12")
    await user.type(screen.getByLabelText("New password"), "a-brand-new-passphrase")
    await user.type(screen.getByLabelText("New password again"), "something-else-entirely")
    await user.click(screen.getByRole("button", { name: "Reset password" }))

    expect(await screen.findByText("Enter the 6-digit code")).toBeInTheDocument()
    expect(screen.getByText("The passwords don’t match")).toBeInTheDocument()
    expect(authApi.confirmPasswordReset).not.toHaveBeenCalled()
  })

  it("goes back to send a new code", async () => {
    const user = userEvent.setup()
    renderPage()
    await askForCode(user)

    await user.click(screen.getByRole("button", { name: "No code? Send a new one" }))

    expect(await screen.findByLabelText("Email")).toBeInTheDocument()
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument()
  })
})
