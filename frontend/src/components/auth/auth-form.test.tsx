import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { AuthForm, type AuthMode } from "@/components/auth/auth-form"

function renderForm(mode: AuthMode, submitting = false) {
  const onSubmit = vi.fn()
  render(<AuthForm mode={mode} submitting={submitting} onSubmit={onSubmit} />)
  return { user: userEvent.setup(), onSubmit }
}

describe("AuthForm", () => {
  it("asks for email and password before signing in, without a name field", async () => {
    const { user, onSubmit } = renderForm("login")
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Sign in" }))

    expect(await screen.findByText("Enter your email")).toBeInTheDocument()
    expect(screen.getByText("Use at least 8 characters")).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("rejects a malformed email and a short password", async () => {
    const { user, onSubmit } = renderForm("login")
    await user.type(screen.getByLabelText("Email"), "not-an-email")
    await user.type(screen.getByLabelText("Password"), "short")
    await user.click(screen.getByRole("button", { name: "Sign in" }))

    expect(await screen.findByText("Enter a valid email")).toBeInTheDocument()
    expect(screen.getByText("Use at least 8 characters")).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("submits trimmed credentials", async () => {
    const { user, onSubmit } = renderForm("login")
    await user.type(screen.getByLabelText("Email"), "  alex@example.com ")
    await user.type(screen.getByLabelText("Password"), "correct-horse")
    await user.click(screen.getByRole("button", { name: "Sign in" }))

    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toEqual({ name: "", email: "alex@example.com", password: "correct-horse" })
  })

  it("requires a name when registering", async () => {
    const { user, onSubmit } = renderForm("register")
    await user.type(screen.getByLabelText("Email"), "alex@example.com")
    await user.type(screen.getByLabelText("Password"), "correct-horse")
    await user.click(screen.getByRole("button", { name: "Create account" }))

    expect(await screen.findByText("Enter your name")).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()

    await user.type(screen.getByLabelText("Name"), "Alex")
    await user.click(screen.getByRole("button", { name: "Create account" }))
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ name: "Alex" })
  })

  it("disables the form while submitting", () => {
    renderForm("login", true)
    expect(screen.getByLabelText("Email")).toBeDisabled()
    expect(screen.getByRole("button", { name: /Sign in/ })).toBeDisabled()
  })
})
