import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ErrorBoundary } from "@/components/layout/error-boundary"

let broken = true

function Page() {
  if (broken) throw new Error("bad state")
  return <p>Food page</p>
}

beforeEach(() => {
  broken = true
  // React and the boundary both report the error; keep the test output quiet.
  vi.spyOn(console, "error").mockImplementation(() => undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe("ErrorBoundary", () => {
  it("shows a way out instead of a blank page", () => {
    render(
      <ErrorBoundary>
        <Page />
      </ErrorBoundary>,
    )

    expect(screen.getByText("Something went wrong on this page")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument()
    expect(console.error).toHaveBeenCalledWith("A page failed to render", expect.any(Error), expect.anything())
  })

  it("renders the page again on Try again", async () => {
    const user = userEvent.setup()
    render(
      <ErrorBoundary>
        <Page />
      </ErrorBoundary>,
    )

    broken = false
    await user.click(screen.getByRole("button", { name: "Try again" }))

    expect(screen.getByText("Food page")).toBeInTheDocument()
  })

  it("shows the page when nothing breaks", () => {
    broken = false
    render(
      <ErrorBoundary>
        <Page />
      </ErrorBoundary>,
    )
    expect(screen.getByText("Food page")).toBeInTheDocument()
  })
})
