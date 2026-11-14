import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { RestTimer } from "@/components/workout/rest-timer"
import { parseRestInput, restLabel } from "@/lib/rest-input"

describe("RestTimer", () => {
  it("offers presets with the suggested rest highlighted, and starts only when one is picked", async () => {
    const dispatch = vi.fn()
    render(<RestTimer rest={null} suggestedSeconds={150} dispatch={dispatch} />)

    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual(["60s", "90s", "2m", "2:30", "3m", "Custom"])
    expect(screen.getByRole("button", { name: "Rest 2:30 (suggested)" })).toBeInTheDocument()
    expect(dispatch).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole("button", { name: "Rest 3:00" }))
    expect(dispatch).toHaveBeenCalledWith({ type: "start-rest", seconds: 180, now: expect.any(Number) })
  })

  it("starts a custom rest and rejects one it can't read", async () => {
    const dispatch = vi.fn()
    render(<RestTimer rest={null} suggestedSeconds={90} dispatch={dispatch} />)

    await userEvent.click(screen.getByRole("button", { name: "Custom" }))
    await userEvent.type(screen.getByRole("textbox", { name: "Custom rest" }), "lots{Enter}")
    expect(screen.getByRole("alert")).toHaveTextContent("like 75 or 2:30")
    expect(dispatch).not.toHaveBeenCalled()

    await userEvent.clear(screen.getByRole("textbox", { name: "Custom rest" }))
    await userEvent.type(screen.getByRole("textbox", { name: "Custom rest" }), "1:45{Enter}")
    expect(dispatch).toHaveBeenCalledWith({ type: "start-rest", seconds: 105, now: expect.any(Number) })
  })

  it("shows the countdown with adjust and skip once a rest is running", async () => {
    const dispatch = vi.fn()
    render(<RestTimer rest={{ endsAt: Date.now() + 60_000, totalSeconds: 60 }} suggestedSeconds={90} dispatch={dispatch} />)
    expect(screen.getByRole("timer")).toHaveTextContent("1:00")
    await userEvent.click(screen.getByRole("button", { name: "Skip" }))
    expect(dispatch).toHaveBeenCalledWith({ type: "skip-rest" })
  })
})

describe("rest input and labels", () => {
  it.each([
    ["75", 75],
    ["75s", 75],
    ["2m", 120],
    ["1.5m", 90],
    ["2:30", 150],
    ["4", null],
    ["11m", null],
    ["2:75", null],
    ["", null],
  ])("reads %j as %j seconds", (input, seconds) => {
    expect(parseRestInput(input)).toBe(seconds)
  })

  it("labels short rests in seconds and longer ones in minutes", () => {
    expect([45, 60, 90, 120, 150, 180].map(restLabel)).toEqual(["45s", "60s", "90s", "2m", "2:30", "3m"])
  })
})
