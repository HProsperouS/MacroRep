import { screen, waitFor } from "@testing-library/react"
import userEvent, { type UserEvent } from "@testing-library/user-event"
import { AxiosError } from "axios"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import OnboardingPage from "@/pages/onboarding-page"
import { renderWithQuery } from "@/test/render"
import type { Profile } from "@/types/profile"

const profileApi = vi.hoisted(() => ({ getProfile: vi.fn(), setTimezone: vi.fn(), completeOnboarding: vi.fn(), estimateTargets: vi.fn() }))
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
  dateOfBirth: null,
  sex: null,
  activityLevel: null,
}
const ESTIMATE = { calories: 1950, protein: 134, carbs: 214, fat: 54, resting: 1480, maintenance: 2294, adjustment: -550 }

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

/** The first step: born 20 April 1995, female, 168 cm, the given weight. */
async function fillAboutYou(user: UserEvent, weight = "72.4") {
  await user.type(await screen.findByLabelText("Date of birth"), "1995-04-20")
  await user.click(screen.getByRole("radio", { name: "Female" }))
  await user.type(screen.getByLabelText("Height"), "168")
  await user.type(screen.getByLabelText("Weight today"), weight)
}

/** The training step: intermediate, 4 days a week, moderately active. */
async function fillTraining(user: UserEvent) {
  await user.click(screen.getByRole("radio", { name: "Intermediate" }))
  await user.type(screen.getByLabelText("Training days"), "4")
  await user.click(screen.getByRole("combobox", { name: "Activity level" }))
  await user.click(await screen.findByRole("option", { name: "Moderately active, exercise 3–5 days a week" }))
}

/** Fills in every step up to the last, with a goal to lose 0.5 kg a week. */
async function fillUpToTargets(user: UserEvent) {
  await fillAboutYou(user)
  await continueTo(user, "Your goal")
  await user.click(screen.getByRole("radio", { name: "Lose fat" }))
  await continueTo(user, "Training")
  await fillTraining(user)
  await continueTo(user, "Equipment")
  await user.click(screen.getByRole("button", { name: "Barbell" }))
  await continueTo(user, "Daily targets")
  await waitFor(() => expect(screen.getByRole("button", { name: "Finish setup" })).toBeEnabled())
}

beforeEach(() => {
  profileApi.getProfile.mockResolvedValue(newProfile)
  profileApi.completeOnboarding.mockImplementation((input) => Promise.resolve({ ...newProfile, ...input, onboarded: true }))
  profileApi.estimateTargets.mockResolvedValue(ESTIMATE)
  foodApi.getTargets.mockResolvedValue({ calories: 2200, protein: 150, carbs: 230, fat: 70 })
})

describe("OnboardingPage", () => {
  it("walks through every step and saves them together, then opens the app", async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText("Step 1 of 5")).toBeInTheDocument()
    expect(screen.getByLabelText("Name")).toHaveValue("Sam")
    await fillUpToTargets(user)
    expect(profileApi.estimateTargets).toHaveBeenCalledWith({
      heightCm: 168,
      weightKg: 72.4,
      dateOfBirth: "1995-04-20",
      sex: "female",
      activityLevel: "moderate",
      goal: "lose",
      weeklyRateKg: -0.5,
    })
    expect(screen.getByLabelText("Calories")).toHaveValue("1950")
    expect(screen.getByText(/1,480 kcal a day at rest, 2,294 kcal to maintain with your activity, −550 kcal a day for your goal/)).toBeInTheDocument()
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
      dateOfBirth: "1995-04-20",
      sex: "female",
      activityLevel: "moderate",
      weightKg: 72.4,
      targets: { calories: 1900, protein: 134, carbs: 214, fat: 54 },
    })
    expect(toast.success).toHaveBeenCalledWith("You’re all set")
  })

  it("doesn't move on until the step is filled in", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Continue" }))
    expect(await screen.findByText("Enter your height")).toBeInTheDocument()
    expect(screen.getByText("Enter your weight")).toBeInTheDocument()
    expect(screen.getByText("Enter your date of birth")).toBeInTheDocument()
    expect(screen.getByText("Choose one")).toBeInTheDocument()
    expect(screen.getByText("Step 1 of 5")).toBeInTheDocument()

    await fillAboutYou(user, "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("button", { name: "Continue" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a goal")
    await user.click(screen.getByRole("radio", { name: "Maintain" }))
    await continueTo(user, "Training")
    await user.click(screen.getByRole("button", { name: "Continue" }))
    expect(await screen.findByText("Enter your training days")).toBeInTheDocument()
    expect(screen.getByText("Choose how active you are")).toBeInTheDocument()
  })

  it("only takes ages the estimate is meant for", async () => {
    const user = userEvent.setup()
    renderPage()
    const tooYoung = `${new Date().getFullYear() - 10}-01-01`

    await user.type(await screen.findByLabelText("Date of birth"), tooYoung)
    await user.click(screen.getByRole("button", { name: "Continue" }))

    expect(await screen.findByText("You need to be 13–100 years old")).toBeInTheDocument()
  })

  it("keeps targets the user changed when going back without changing any details, and estimates again after", async () => {
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)
    await user.clear(screen.getByLabelText("Calories"))
    await user.type(screen.getByLabelText("Calories"), "2000")

    await user.click(screen.getByRole("button", { name: "Back" }))
    await continueTo(user, "Daily targets")
    expect(screen.getByLabelText("Calories")).toHaveValue("2000")
    expect(profileApi.estimateTargets).toHaveBeenCalledOnce()

    for (let back = 0; back < 4; back++) await user.click(screen.getByRole("button", { name: "Back" }))
    await user.clear(await screen.findByLabelText("Weight today"))
    await user.type(screen.getByLabelText("Weight today"), "70")
    profileApi.estimateTargets.mockResolvedValue({ ...ESTIMATE, calories: 1900 })
    for (const title of ["Your goal", "Training", "Equipment", "Daily targets"]) await continueTo(user, title)
    expect(screen.getByLabelText("Calories")).toHaveValue("1900")
  })

  it("goes back to general targets when a later estimate fails, and tries again next time", async () => {
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)
    expect(screen.getByLabelText("Calories")).toHaveValue("1950")

    for (let back = 0; back < 4; back++) await user.click(screen.getByRole("button", { name: "Back" }))
    await user.clear(await screen.findByLabelText("Weight today"))
    await user.type(screen.getByLabelText("Weight today"), "60")
    profileApi.estimateTargets.mockRejectedValueOnce(new Error("offline"))
    for (const title of ["Your goal", "Training", "Equipment", "Daily targets"]) await continueTo(user, title)
    expect(screen.getByLabelText("Calories")).toHaveValue("2200")
    expect(screen.getByText(/general starting targets/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Back" }))
    await continueTo(user, "Daily targets")
    expect(screen.getByLabelText("Calories")).toHaveValue("1950")
    expect(profileApi.estimateTargets).toHaveBeenCalledTimes(3)
  })

  it("falls back to general targets, and says so, when no estimate comes back", async () => {
    profileApi.estimateTargets.mockRejectedValue(new Error("offline"))
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)

    expect(screen.getByLabelText("Calories")).toHaveValue("2200")
    expect(screen.getByText(/general starting targets/)).toBeInTheDocument()
  })

  it("keeps what was entered when going back", async () => {
    const user = userEvent.setup()
    renderPage()

    await fillAboutYou(user, "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("button", { name: "Back" }))

    expect(await screen.findByLabelText("Height")).toHaveValue("168")
    expect(screen.getByLabelText("Weight today")).toHaveValue("72")
  })

  it("refuses targets whose calories are far below their macros", async () => {
    const user = userEvent.setup()
    renderPage()
    await fillUpToTargets(user)

    await user.clear(screen.getByLabelText("Protein"))
    await user.type(screen.getByLabelText("Protein"), "400")
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
    for (let back = 0; back < 4; back++) await user.click(screen.getByRole("button", { name: "Back" }))
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
    await fillAboutYou(user, "72")
    await continueTo(user, "Your goal")
    await user.click(screen.getByRole("radio", { name: "Maintain" }))
    await continueTo(user, "Training")
    await fillTraining(user)
    await continueTo(user, "Equipment")

    await user.dblClick(screen.getByRole("button", { name: "Continue" }))

    expect(await screen.findByRole("heading", { name: "Daily targets" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Finish setup" })).toBeDisabled()
    expect(profileApi.completeOnboarding).not.toHaveBeenCalled()
  })

  it("lets maintain through even after an invalid rate for another goal", async () => {
    const user = userEvent.setup()
    renderPage()
    await fillAboutYou(user, "72")
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
