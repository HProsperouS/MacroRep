import { screen, waitFor } from "@testing-library/react"
import userEvent, { type UserEvent } from "@testing-library/user-event"
import { AxiosError } from "axios"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OnboardingPage from "@/pages/onboarding-page"
import { renderWithQuery } from "@/test/render"
import type { Profile } from "@/types/profile"

const profileApi = vi.hoisted(() => ({ getProfile: vi.fn(), setTimezone: vi.fn(), completeOnboarding: vi.fn() }))
const foodApi = vi.hoisted(() => ({ getTargets: vi.fn() }))
vi.mock("@/api/profile-api", () => ({ profileApi }))
vi.mock("@/api/food-api", () => ({ foodApi }))

const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
const newProfile: Profile = {
  name: "Sam",
  email: "sam@example.com",
  heightCm: 170,
  goal: "maintain",
  weeklyRateKg: 0,
  trainingDaysPerWeek: 3,
  experienceLevel: "beginner",
  equipment: [],
  timezone,
  onboarded: false,
}

function renderPage() {
  return renderWithQuery(
    <MemoryRouter initialEntries={["/welcome"]}>
      <Routes>
        <Route path="/welcome" element={<OnboardingPage />} />
        <Route path="/" element={<h1>Home page</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

async function continueTo(user: UserEvent, title: string) {
  await user.click(screen.getByRole("button", { name: "Continue" }))
  expect(await screen.findByRole("heading", { name: title })).toHaveFocus()
}

/** Fills in every step up to the last, with a goal to lose 0.5 kg a week. */
async function fillUpToTargets(user: UserEvent) {
  await user.type(await screen.findByLabelText("Height"), "168")
  await user.type(screen.getByLabelText("Weight today"), "72.4")
  await continueTo(user, "Your goal")
  await user.click(screen.getByRole("radio", { name: "Lose fat" }))
  await continueTo(user, "Training")
  await user.click(screen.getByRole("radio", { name: "Intermediate" }))
  await user.type(screen.getByLabelText("Training days"), "4")
  await continueTo(user, "Equipment")
  await user.click(screen.getByRole("button", { name: "Barbell" }))
  await continueTo(user, "Daily targets")
  await waitFor(() => expect(screen.getByRole("button", { name: "Finish setup" })).toBeEnabled())
}

beforeEach(() => {
  profileApi.getProfile.mockResolvedValue(newProfile)
  profileApi.completeOnboarding.mockImplementation((input) => Promise.resolve({ ...newProfile, ...input, onboarded: true }))
  foodApi.getTargets.mockResolvedValue({ calories: 2200, protein: 150, carbs: 230, fat: 70 })
})

describe("OnboardingPage", () => {
  it("walks through every step and saves them together, then opens the app", async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText("Step 1 of 5")).toBeInTheDocument()
    expect(screen.getByLabelText("Name")).toHaveValue("Sam")
    await fillUpToTargets(user)
    expect(screen.getByLabelText("Calories")).toHaveValue("2200")
    await user.clear(screen.getByLabelText("Calories"))
    await user.type(screen.getByLabelText("Calories"), "1900")
    await user.click(screen.getByRole("button", { name: "Finish setup" }))

    expect(await screen.findByRole("heading", { name: "Home page" })).toBeInTheDocument()
    expect(profileApi.completeOnboarding).toHaveBeenCalledWith({
      name: "Sam",
      heightCm: 168,
      goal: "lose",
      weeklyRateKg: -0.5,
      trainingDaysPerWeek: 4,
      experienceLevel: "intermediate",
      equipment: ["barbell"],
      weightKg: 72.4,
      targets: { calories: 1900, protein: 150, carbs: 230, fat: 70 },
    })
    expect(toast.success).toHaveBeenCalledWith("You’re all set")
  })

  it("doesn't move on until the step is filled in", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Continue" }))
    expect(await screen.findByText("Enter your height")).toBeInTheDocument()
    expect(screen.getByText("Enter your weight")).toBeInTheDocument()
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument()

    await user.type(screen.getByLabelText("Height"), "168")
    await user.type(screen.getByLabelText("Weight today"), "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("button", { name: "Continue" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a goal")
    await user.click(screen.getByRole("radio", { name: "Maintain" }))
    await continueTo(user, "Training")
    await user.click(screen.getByRole("button", { name: "Continue" }))
    expect(await screen.findByText("Enter your training days")).toBeInTheDocument()
  })

  it("keeps what was entered when going back", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(await screen.findByLabelText("Height"), "168")
    await user.type(screen.getByLabelText("Weight today"), "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("button", { name: "Back" }))

    expect(await screen.findByLabelText("Height")).toHaveValue("168")
    expect(screen.getByLabelText("Weight today")).toHaveValue("72")
  })

  it("refuses targets whose calories are far below their macros", async () => {
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)

    await user.clear(screen.getByLabelText("Calories"))
    await user.type(screen.getByLabelText("Calories"), "1000")
    await user.click(screen.getByRole("button", { name: "Finish setup" }))

    expect(await screen.findByText(/Too low for these macros/)).toBeInTheDocument()
    expect(profileApi.completeOnboarding).not.toHaveBeenCalled()
  })

  it("says why setting up failed, and keeps everything entered even when the profile can't be reloaded", async () => {
    profileApi.completeOnboarding.mockRejectedValue(
      new AxiosError("409", "ERR_BAD_REQUEST", undefined, undefined, { status: 409, data: { detail: "Something broke." } } as never),
    )
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)
    profileApi.getProfile.mockRejectedValue(new Error("offline")) // the check after the 409 fails too

    await user.click(screen.getByRole("button", { name: "Finish setup" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t finish setting up", { description: "Something broke." }))
    await waitFor(() => expect(profileApi.getProfile).toHaveBeenCalledTimes(2))
    expect(screen.getByRole("heading", { name: "Daily targets" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Back" }))
    await user.click(screen.getByRole("button", { name: "Back" }))
    await user.click(screen.getByRole("button", { name: "Back" }))
    await user.click(screen.getByRole("button", { name: "Back" }))
    expect(await screen.findByLabelText("Height")).toHaveValue("168")
  })

  it("opens the app without an error when the guide was already finished elsewhere", async () => {
    profileApi.completeOnboarding.mockRejectedValue(
      new AxiosError("409", "ERR_BAD_REQUEST", undefined, undefined, { status: 409, data: { detail: "Already set up." } } as never),
    )
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)
    profileApi.getProfile.mockResolvedValue({ ...newProfile, onboarded: true })

    await user.click(screen.getByRole("button", { name: "Finish setup" }))

    expect(await screen.findByRole("heading", { name: "Home page" })).toBeInTheDocument()
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("says so when a 409 was a clash with another change, not a finished guide", async () => {
    const detail = "Your weight or targets were just changed elsewhere, please retry"
    profileApi.completeOnboarding.mockRejectedValue(new AxiosError("409", "ERR_BAD_REQUEST", undefined, undefined, { status: 409, data: { detail } } as never))
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)

    await user.click(screen.getByRole("button", { name: "Finish setup" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t finish setting up", { description: detail }))
    expect(screen.getByRole("heading", { name: "Daily targets" })).toBeInTheDocument()
  })

  it("holds Finish back for a moment, so a double click on Continue doesn't submit", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(await screen.findByLabelText("Height"), "168")
    await user.type(screen.getByLabelText("Weight today"), "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("radio", { name: "Maintain" }))
    await continueTo(user, "Training")
    await user.click(screen.getByRole("radio", { name: "Beginner" }))
    await user.type(screen.getByLabelText("Training days"), "3")
    await continueTo(user, "Equipment")

    await user.dblClick(screen.getByRole("button", { name: "Continue" }))

    expect(await screen.findByRole("heading", { name: "Daily targets" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Finish setup" })).toBeDisabled()
    expect(profileApi.completeOnboarding).not.toHaveBeenCalled()
  })

  it("lets maintain through even after an invalid rate for another goal", async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(await screen.findByLabelText("Height"), "168")
    await user.type(screen.getByLabelText("Weight today"), "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("radio", { name: "Lose fat" }))
    await user.clear(screen.getByLabelText("Loss per week"))
    await user.type(screen.getByLabelText("Loss per week"), "abc")
    await user.click(screen.getByRole("button", { name: "Continue" }))
    expect(await screen.findByText("Enter a number")).toBeInTheDocument()
    await user.click(screen.getByRole("radio", { name: "Maintain" }))
    await user.click(screen.getByRole("radio", { name: "Lose fat" }))
    expect(screen.queryByText("Enter a number")).not.toBeInTheDocument()
    await user.click(screen.getByRole("radio", { name: "Maintain" }))

    await continueTo(user, "Training")
  })

  it("sends a user who has already set up to the app", async () => {
    profileApi.getProfile.mockResolvedValue({ ...newProfile, onboarded: true })
    renderPage()

    expect(await screen.findByRole("heading", { name: "Home page" })).toBeInTheDocument()
  })
})
