import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ExercisePicker } from "@/components/workout/exercise-picker"
import { renderWithQuery } from "@/test/render"
import type { Exercise } from "@/types/workout"

const api = vi.hoisted(() => ({ searchExercises: vi.fn(), createExercise: vi.fn() }))
vi.mock("@/api/workout-api", () => ({ workoutApi: api }))

const bench: Exercise = {
  id: "bench",
  name: "Bench Press",
  equipment: "barbell",
  muscles: ["chest", "triceps"],
  source: "library",
  lastSession: { date: "2026-10-16", sets: [{ weightKg: 60, reps: 8 }, { weightKg: 62.5, reps: 6 }] as never },
}
const pushUp: Exercise = { id: "push-up", name: "Push-up", equipment: "bodyweight", muscles: ["chest"], source: "custom", lastSession: { date: "2026-10-15", sets: [{ weightKg: 0, reps: 20 }] as never } }

function renderPicker() {
  const onAdd = vi.fn()
  renderWithQuery(<ExercisePicker onAdd={onAdd} />)
  return { onAdd, user: userEvent.setup() }
}

beforeEach(() => {
  api.searchExercises.mockImplementation(({ q, muscle }: { q: string; muscle?: string }) =>
    Promise.resolve([bench, pushUp].filter((exercise) => exercise.name.toLowerCase().includes(q.toLowerCase()) && (!muscle || exercise.muscles.includes(muscle as never)))),
  )
})

describe("ExercisePicker", () => {
  it("shows each exercise with its best recent set", async () => {
    renderPicker()
    expect(await screen.findByText(/Barbell · Chest, Triceps · Last: 60 kg × 8 · 16 Oct/)).toBeInTheDocument()
    expect(screen.getByText(/Bodyweight · Chest · Last: 20 reps · 15 Oct/)).toBeInTheDocument()
    expect(screen.getByText("Custom")).toBeInTheDocument()
  })

  it("adds the selected exercises in the order they were picked", async () => {
    const { onAdd, user } = renderPicker()
    expect(screen.getByRole("button", { name: "Select exercises" })).toBeDisabled()

    await user.click(await screen.findByRole("button", { name: /Push-up/ }))
    await user.click(screen.getByRole("button", { name: /Bench Press/ }))
    await user.click(screen.getByRole("button", { name: /Push-up/ }))
    await user.click(screen.getByRole("button", { name: /Push-up/ }))
    expect(screen.getByRole("button", { name: /Bench Press/ })).toHaveAttribute("aria-pressed", "true")
    await user.click(screen.getByRole("button", { name: "Add 2 exercises" }))

    expect(onAdd).toHaveBeenCalledWith([bench, pushUp])
  })

  it("filters by muscle and offers to clear filters that match nothing", async () => {
    const { user } = renderPicker()
    await screen.findByText("Bench Press")

    await user.click(screen.getByRole("combobox", { name: "Filter by muscle" }))
    await user.click(await screen.findByRole("option", { name: "Back" }))

    expect(await screen.findByText("No exercises match these filters")).toBeInTheDocument()
    expect(api.searchExercises).toHaveBeenLastCalledWith({ q: "", muscle: "back", equipment: undefined }, expect.anything())
    await user.click(screen.getByRole("button", { name: "Clear filters" }))
    expect(await screen.findByText("Bench Press")).toBeInTheDocument()
  })

  it("creates a custom exercise named after the search and adds it", async () => {
    const row: Exercise = { id: "row", name: "Seal row", equipment: "barbell", muscles: ["back"], source: "custom" }
    api.createExercise.mockResolvedValue(row)
    const { onAdd, user } = renderPicker()

    await user.type(screen.getByRole("searchbox", { name: "Search exercises" }), "Seal row")
    expect(await screen.findByText("No exercises match “Seal row”")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Create “Seal row”" }))

    expect(screen.getByLabelText("Name")).toHaveValue("Seal row")
    await user.click(screen.getByRole("button", { name: "Create and add" }))
    expect(await screen.findByText("Choose the equipment")).toBeInTheDocument()
    expect(screen.getByText("Choose at least one muscle group")).toBeInTheDocument()

    await user.click(screen.getByRole("combobox", { name: "Equipment" }))
    await user.click(await screen.findByRole("option", { name: "Barbell" }))
    await user.click(screen.getByRole("button", { name: "Back" }))
    await user.click(screen.getByRole("button", { name: "Create and add" }))

    await waitFor(() => expect(api.createExercise).toHaveBeenCalledWith({ name: "Seal row", equipment: "barbell", muscles: ["back"] }))
    expect(onAdd).toHaveBeenCalledWith([row])
    expect(toast.success).toHaveBeenCalledWith("Created Seal row", expect.anything())
  })

  it("goes back to the search from the create form", async () => {
    const { user } = renderPicker()
    await user.click(await screen.findByRole("button", { name: "Create exercise" }))
    await user.click(screen.getByRole("button", { name: "Back to search" }))
    expect(screen.getByRole("searchbox", { name: "Search exercises" })).toBeInTheDocument()
  })

  it("keeps the form open when creating fails", async () => {
    api.createExercise.mockRejectedValue(new Error("down"))
    const { onAdd, user } = renderPicker()

    await user.click(await screen.findByRole("button", { name: "Create exercise" }))
    await user.type(screen.getByLabelText("Name"), "Seal row")
    await user.click(screen.getByRole("combobox", { name: "Equipment" }))
    await user.click(await screen.findByRole("option", { name: "Barbell" }))
    await user.click(screen.getByRole("button", { name: "Back" }))
    await user.click(screen.getByRole("button", { name: "Create and add" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t create that exercise", expect.anything()))
    expect(onAdd).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Create and add" })).toBeInTheDocument()
  })

  it("offers a retry when the library can't be loaded", async () => {
    api.searchExercises.mockRejectedValueOnce(new Error("down"))
    const { user } = renderPicker()

    expect(await screen.findByText("Couldn’t load exercises")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("Bench Press")).toBeInTheDocument()
  })
})
