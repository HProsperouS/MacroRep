import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ExerciseNote } from "@/components/workout/exercise-note"
import { renderWithQuery } from "@/test/render"

const api = vi.hoisted(() => ({ saveExerciseNote: vi.fn() }))
vi.mock("@/api/workout-api", () => ({ workoutApi: api }))

const bench = { exerciseId: "bench", name: "Bench Press" }

describe("ExerciseNote", () => {
  beforeEach(() => {
    api.saveExerciseNote.mockReset().mockResolvedValue({ exerciseId: "bench", body: "" })
  })

  it("shows a saved note and saves an edit when the field loses focus", async () => {
    const dispatch = vi.fn()
    renderWithQuery(<ExerciseNote exercise={{ ...bench, userNote: "Seat on 4" }} dispatch={dispatch} />)

    await userEvent.click(screen.getByRole("button", { name: "Edit note for Bench Press" }))
    const field = screen.getByRole("textbox", { name: "Note for Bench Press" })
    expect(field).toHaveValue("Seat on 4")
    await userEvent.clear(field)
    await userEvent.type(field, "Seat on 5 ")
    await userEvent.tab()

    expect(dispatch).toHaveBeenCalledWith({ type: "edit-note", exerciseId: "bench", value: "Seat on 5" })
    await waitFor(() => expect(api.saveExerciseNote).toHaveBeenCalledWith("bench", "Seat on 5"))
  })

  it("adds a note when there is none, and saves nothing if it's unchanged", async () => {
    const dispatch = vi.fn()
    renderWithQuery(<ExerciseNote exercise={{ ...bench, userNote: "" }} dispatch={dispatch} />)

    await userEvent.click(screen.getByRole("button", { name: "Add note" }))
    await userEvent.tab()
    expect(dispatch).not.toHaveBeenCalled()
    expect(api.saveExerciseNote).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Add note" })).toBeInTheDocument()
  })

  it("throws away the edit on Escape", async () => {
    const dispatch = vi.fn()
    renderWithQuery(<ExerciseNote exercise={{ ...bench, userNote: "Seat on 4" }} dispatch={dispatch} />)
    await userEvent.click(screen.getByRole("button", { name: "Edit note for Bench Press" }))
    await userEvent.type(screen.getByRole("textbox", { name: "Note for Bench Press" }), " and more{Escape}")
    expect(screen.getByRole("button", { name: "Edit note for Bench Press" })).toHaveTextContent("Seat on 4")
    expect(dispatch).not.toHaveBeenCalled()
  })
})
