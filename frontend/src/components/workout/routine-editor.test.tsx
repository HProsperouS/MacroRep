import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { RoutineEditor } from "@/components/workout/routine-editor"
import { plannedExercise, routine } from "@/test/routines"
import type { Routine } from "@/types/workout"

vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true, useOverlayLayout: () => "dialog" }))
// The exercise picker talks to the API; these tests don't open it.
vi.mock("@/components/workout/exercise-picker", () => ({ ExercisePicker: () => null }))

function renderEditor(existing: Routine | null, scheduledDays: number[] = []) {
  const handlers = { onSave: vi.fn(), onDelete: vi.fn(), onCancel: vi.fn() }
  render(<RoutineEditor routine={existing} scheduledDays={scheduledDays} submitting={false} deleting={false} {...handlers} />)
  return { user: userEvent.setup(), ...handlers }
}

const twoExercises = routine("r1", "Push", [], [plannedExercise("bench", "Bench Press"), plannedExercise("ohp", "Overhead Press")])

describe("RoutineEditor", () => {
  it("saves an edited routine with its exercises and sets", async () => {
    const { user, onSave } = renderEditor(routine("r1", "Push"))
    const name = screen.getByLabelText("Name")
    await user.clear(name)
    await user.type(name, "Push A")
    await user.click(screen.getByRole("button", { name: "Save routine" }))

    expect(onSave).toHaveBeenCalledWith({
      name: "Push A",
      exercises: [
        {
          exerciseId: "bench",
          restSeconds: 90,
          sets: [
            { kind: "warmup", targetWeightKg: 40, targetReps: 10 },
            { kind: "working", targetWeightKg: 60, targetReps: 8 },
          ],
        },
      ],
    })
  })

  it("reorders exercises", async () => {
    const { user, onSave } = renderEditor(twoExercises)
    await user.click(screen.getByRole("button", { name: "Move Overhead Press up" }))
    await user.click(screen.getByRole("button", { name: "Save routine" }))
    expect(onSave.mock.calls[0][0].exercises.map((exercise: { exerciseId: string }) => exercise.exerciseId)).toEqual(["ohp", "bench"])
  })

  it("can't move the first exercise up or the last one down", () => {
    renderEditor(twoExercises)
    expect(screen.getByRole("button", { name: "Move Bench Press up" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Move Overhead Press down" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Move Bench Press down" })).toBeEnabled()
  })

  it.each([
    ["Rest between sets", "700", "0–600"],
    ["Rest between sets", "1.5", "Whole number"],
    ["Rest between sets", "lots", "Enter a number"],
  ])("won't save %s of %s, which the server would refuse", async (label, value, message) => {
    const { user, onSave } = renderEditor(routine("r1", "Push"))
    const field = screen.getByLabelText(label)
    await user.clear(field)
    await user.type(field, value)

    expect(screen.getByText(message)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save routine" })).toBeDisabled()
    expect(onSave).not.toHaveBeenCalled()
  })

  it("won't save a target the server would refuse", async () => {
    const { user } = renderEditor(routine("r1", "Push"))
    const [, reps] = screen.getAllByPlaceholderText("Target").filter((input) => input.id.endsWith("-reps"))
    await user.clear(reps)
    await user.type(reps, "150")

    expect(screen.getByText("1–100")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save routine" })).toBeDisabled()
  })

  it("needs a name to save", async () => {
    const { user, onSave } = renderEditor(routine("r1", "Push"))
    await user.clear(screen.getByLabelText("Name"))
    expect(screen.getByText("Give the routine a name")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save routine" })).toBeDisabled()
    expect(onSave).not.toHaveBeenCalled()
  })

  it("trims the name", async () => {
    const { user, onSave } = renderEditor(routine("r1", "Push"))
    await user.type(screen.getByLabelText("Name"), "  ")
    await user.click(screen.getByRole("button", { name: "Save routine" }))
    expect(onSave.mock.calls[0][0].name).toBe("Push")
  })

  it("starts a new routine empty and can't save it until it has an exercise", () => {
    renderEditor(null)
    expect(screen.getByLabelText("Name")).toHaveValue("New routine")
    expect(screen.getByText("No exercises yet")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Save routine" })).toBeDisabled()
    expect(screen.queryByRole("button", { name: "Delete routine" })).not.toBeInTheDocument()
  })

  it("removes an exercise", async () => {
    const { user, onSave } = renderEditor(twoExercises)
    await user.click(screen.getByRole("button", { name: "Remove Bench Press" }))
    await user.click(screen.getByRole("button", { name: "Save routine" }))
    expect(onSave.mock.calls[0][0].exercises.map((exercise: { exerciseId: string }) => exercise.exerciseId)).toEqual(["ohp"])
  })

  it("asks before deleting and says which days become rest days", async () => {
    const { user, onDelete } = renderEditor(routine("r1", "Push"), [0, 4])
    await user.click(screen.getByRole("button", { name: "Delete routine" }))

    const dialog = await screen.findByRole("dialog", { name: "Delete this routine?" })
    expect(dialog).toHaveTextContent("Monday, Friday")
    expect(onDelete).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole("button", { name: "Delete routine" }))
    expect(onDelete).toHaveBeenCalledOnce()
  })

  it("keeps the routine when the delete is cancelled", async () => {
    const { user, onDelete } = renderEditor(routine("r1", "Push"))
    await user.click(screen.getByRole("button", { name: "Delete routine" }))
    const dialog = await screen.findByRole("dialog")
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }))
    expect(onDelete).not.toHaveBeenCalled()
  })
})
