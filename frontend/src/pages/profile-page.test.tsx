import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { getAccessToken, setAccessToken } from "@/lib/auth"
import ProfilePage from "@/pages/profile-page"
import { renderWithQuery } from "@/test/render"
import type { Profile } from "@/types/profile"

const profileApi = vi.hoisted(() => ({ getProfile: vi.fn(), updateProfile: vi.fn(), getTargetHistory: vi.fn(), updateTargets: vi.fn() }))
const foodApi = vi.hoisted(() => ({ getTargets: vi.fn() }))
const authApi = vi.hoisted(() => ({ logout: vi.fn() }))
vi.mock("@/api/profile-api", () => ({ profileApi }))
vi.mock("@/api/food-api", () => ({ foodApi }))
vi.mock("@/api/auth-api", () => ({ authApi }))

const profile: Profile = {
  name: "Alex",
  email: "alex@example.com",
  heightCm: 178,
  goal: "lose",
  weeklyRateKg: -0.5,
  trainingDaysPerWeek: 4,
  experienceLevel: "intermediate",
  equipment: ["barbell", "dumbbell"],
  timezone: "UTC",
  onboarded: true,
}

function renderPage() {
  return renderWithQuery(
    <MemoryRouter initialEntries={["/profile"]}>
      <Routes>
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/login" element={<p>Login page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  profileApi.getProfile.mockResolvedValue(profile)
  profileApi.updateProfile.mockImplementation((input) => Promise.resolve({ ...profile, ...input }))
  profileApi.getTargetHistory.mockResolvedValue([])
  profileApi.updateTargets.mockImplementation((input) => Promise.resolve(input))
  foodApi.getTargets.mockResolvedValue({ calories: 2200, protein: 150, carbs: 250, fat: 70 })
})

describe("ProfilePage", () => {
  it("saves the profile, with a loss rate sent as negative", async () => {
    const user = userEvent.setup()
    renderPage()

    const name = await screen.findByLabelText("Name")
    expect(screen.getByRole("button", { name: "Save profile" })).toBeDisabled()
    await user.clear(name)
    await user.type(name, "Alex Tan")
    await user.click(screen.getByRole("radio", { name: "Advanced" }))
    await user.click(screen.getByRole("button", { name: "Cable" }))
    await user.click(screen.getByRole("button", { name: "Save profile" }))

    await waitFor(() =>
      expect(profileApi.updateProfile).toHaveBeenCalledWith({
        name: "Alex Tan",
        heightCm: 178,
        goal: "lose",
        weeklyRateKg: -0.5,
        trainingDaysPerWeek: 4,
        experienceLevel: "advanced",
        equipment: ["barbell", "dumbbell", "cable"],
      }),
    )
    expect(toast.success).toHaveBeenCalledWith("Profile saved")
  })

  it("sends no rate when maintaining", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("radio", { name: "Maintain" }))
    expect(screen.getByLabelText("Loss per week")).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Save profile" }))

    await waitFor(() => expect(profileApi.updateProfile).toHaveBeenCalledWith(expect.objectContaining({ goal: "maintain", weeklyRateKg: 0 })))
  })

  it("cautions about a fast rate, without refusing it", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("radio", { name: "Build muscle" }))
    const rate = screen.getByLabelText("Gain per week")
    await user.clear(rate)
    await user.type(rate, "0.8")
    expect(screen.getByText(/Gaining this quickly tends to add mostly fat/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Save profile" }))

    await waitFor(() => expect(profileApi.updateProfile).toHaveBeenCalledWith(expect.objectContaining({ goal: "gain", weeklyRateKg: 0.8 })))
  })

  it("refuses an out-of-range height and training days", async () => {
    const user = userEvent.setup()
    renderPage()

    await user.clear(await screen.findByLabelText("Height"))
    await user.type(screen.getByLabelText("Height"), "50")
    await user.clear(screen.getByLabelText("Training days"))
    await user.type(screen.getByLabelText("Training days"), "9")
    await user.click(screen.getByRole("button", { name: "Save profile" }))

    expect(await screen.findByText("Must be at least 100")).toBeInTheDocument()
    expect(screen.getByText("At most 7 days")).toBeInTheDocument()
    expect(profileApi.updateProfile).not.toHaveBeenCalled()
  })

  it("reports a failed save", async () => {
    profileApi.updateProfile.mockRejectedValue(new Error("down"))
    const user = userEvent.setup()
    renderPage()

    await user.type(await screen.findByLabelText("Name"), "!")
    await user.click(screen.getByRole("button", { name: "Save profile" }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t save your profile", expect.anything()))
  })

  it("saves the daily targets and checks them against the macros", async () => {
    const user = userEvent.setup()
    renderPage()

    const calories = await screen.findByRole("textbox", { name: "Calories" })
    expect(screen.getByText("Macros add up to 2,230 kcal")).toBeInTheDocument()
    await user.clear(calories)
    await user.type(calories, "2500")
    expect(screen.getByText("Macros add up to 2,230 kcal, which doesn’t match 2,500 kcal.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Save targets" }))

    await waitFor(() => expect(profileApi.updateTargets).toHaveBeenCalledWith({ calories: 2500, protein: 150, carbs: 250, fat: 70 }))
    expect(toast.success).toHaveBeenCalledWith("Targets saved", expect.anything())
  })

  it("refuses calories far below the macros", async () => {
    const user = userEvent.setup()
    renderPage()

    const calories = await screen.findByRole("textbox", { name: "Calories" })
    await user.clear(calories)
    await user.type(calories, "1000")
    await user.click(screen.getByRole("button", { name: "Save targets" }))

    expect(await screen.findByText(/Too low for these macros/)).toBeInTheDocument()
    expect(profileApi.updateTargets).not.toHaveBeenCalled()
  })

  it("shows errors when the profile or targets can't be loaded", async () => {
    profileApi.getProfile.mockRejectedValue(new Error("down"))
    foodApi.getTargets.mockRejectedValue(new Error("down"))
    renderPage()

    expect(await screen.findByText("Couldn’t load your profile")).toBeInTheDocument()
    expect(await screen.findByText("Couldn’t load your targets")).toBeInTheDocument()
  })

  it("signs out even when the server can't be reached", async () => {
    authApi.logout.mockRejectedValue(new Error("offline"))
    setAccessToken("token")
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole("button", { name: "Sign out" }))

    expect(await screen.findByText("Login page")).toBeInTheDocument()
    expect(getAccessToken()).toBeNull()
  })
})
