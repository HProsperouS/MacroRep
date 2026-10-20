import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
import { MemoryRouter } from "react-router-dom"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import App from "@/App"
import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/auth"
import { renderWithQuery } from "@/test/render"

const session = vi.hoisted(() => ({ restoreSession: vi.fn() }))
const authApi = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn(), logout: vi.fn() }))
const profileApi = vi.hoisted(() => ({ getProfile: vi.fn(), setTimezone: vi.fn() }))
vi.mock("@/api/client", async (importOriginal) => ({ ...(await importOriginal<object>()), ...session }))
vi.mock("@/api/auth-api", () => ({ authApi }))
vi.mock("@/api/profile-api", () => ({ profileApi }))
// The pages have their own tests; here they only show which route was reached.
vi.mock("@/pages/home-page", () => ({ default: () => <h1>Home page</h1> }))
vi.mock("@/pages/food-page", () => ({ default: () => <h1>Food page</h1> }))

const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone

function renderAt(url: string) {
  return renderWithQuery(
    <MemoryRouter initialEntries={[url]}>
      <App />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  clearAccessToken()
  session.restoreSession.mockResolvedValue(false)
  profileApi.getProfile.mockResolvedValue({ name: "Alex", timezone })
})

describe("App", () => {
  it("sends a visitor without a session to sign in", async () => {
    renderAt("/food")
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument()
    expect(screen.queryByText("Food page")).not.toBeInTheDocument()
  })

  it("lets a returning visitor in on their refresh cookie", async () => {
    session.restoreSession.mockResolvedValue(true)
    renderAt("/food")
    expect(await screen.findByText("Food page")).toBeInTheDocument()
  })

  it("moves between pages from the navigation", async () => {
    setAccessToken("token")
    const user = userEvent.setup()
    renderAt("/")

    expect(await screen.findByText("Home page")).toBeInTheDocument()
    await user.click(screen.getAllByRole("link", { name: "Food" })[0])
    expect(await screen.findByText("Food page")).toBeInTheDocument()
    expect(session.restoreSession).not.toHaveBeenCalled()
  })

  it("shows a not-found page inside the app", async () => {
    setAccessToken("token")
    renderAt("/nowhere")
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Back to Home" })).toHaveAttribute("href", "/")
  })

  it("bounces a signed-in visitor away from the sign-in form", async () => {
    setAccessToken("token")
    renderAt("/login")
    expect(await screen.findByText("Home page")).toBeInTheDocument()
  })

  it("signs in and opens the app", async () => {
    authApi.login.mockResolvedValue({ accessToken: "fresh", tokenType: "bearer", expiresIn: 900 })
    const user = userEvent.setup()
    renderAt("/login")

    await user.type(await screen.findByLabelText("Email"), "alex@example.com")
    await user.type(screen.getByLabelText("Password"), "long-enough-pw")
    await user.click(screen.getByRole("button", { name: "Sign in" }))

    expect(await screen.findByText("Home page")).toBeInTheDocument()
    expect(authApi.login).toHaveBeenCalledWith({ email: "alex@example.com", password: "long-enough-pw" })
    expect(getAccessToken()).toBe("fresh")
  })

  it("reports a wrong password with the server's message", async () => {
    authApi.login.mockRejectedValue(
      new AxiosError("401", "ERR_BAD_REQUEST", undefined, undefined, { status: 401, data: { message: "Wrong email or password." } } as never),
    )
    const user = userEvent.setup()
    renderAt("/login")

    await user.type(await screen.findByLabelText("Email"), "alex@example.com")
    await user.type(screen.getByLabelText("Password"), "wrong-password")
    await user.click(screen.getByRole("button", { name: "Sign in" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t sign you in", { description: "Wrong email or password." }))
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument()
  })

  it("creates an account and opens the app", async () => {
    authApi.register.mockResolvedValue({ accessToken: "new", tokenType: "bearer", expiresIn: 900 })
    const user = userEvent.setup()
    renderAt("/login")

    await user.click(await screen.findByRole("link", { name: "Create an account" }))
    await user.type(await screen.findByLabelText("Name"), "Alex")
    await user.type(screen.getByLabelText("Email"), "alex@example.com")
    await user.type(screen.getByLabelText("Password"), "long-enough-pw")
    await user.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("Home page")).toBeInTheDocument()
    expect(authApi.register).toHaveBeenCalledWith({ name: "Alex", email: "alex@example.com", password: "long-enough-pw" })
  })

  it("signs out from the sidebar", async () => {
    authApi.logout.mockResolvedValue(undefined)
    setAccessToken("token")
    const user = userEvent.setup()
    renderAt("/")

    await user.click(await screen.findByRole("button", { name: "Sign out" }))
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument()
    expect(getAccessToken()).toBeNull()
  })

  it("moves the profile to this device's timezone, once", async () => {
    profileApi.getProfile.mockResolvedValue({ name: "Alex", timezone: timezone === "Pacific/Chatham" ? "Asia/Singapore" : "Pacific/Chatham" })
    profileApi.setTimezone.mockRejectedValue(new Error("unknown zone"))
    setAccessToken("token")
    renderAt("/")

    await waitFor(() => expect(profileApi.setTimezone).toHaveBeenCalledWith(timezone))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(profileApi.setTimezone).toHaveBeenCalledOnce()
  })

  it("leaves a matching timezone alone", async () => {
    setAccessToken("token")
    renderAt("/")
    await screen.findByText("Home page")
    await waitFor(() => expect(profileApi.getProfile).toHaveBeenCalled())
    expect(profileApi.setTimezone).not.toHaveBeenCalled()
  })
})
