import { render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { WorkoutSummary } from "@/components/workout/workout-summary"
import type { WorkoutSummary as WorkoutSummaryData } from "@/types/workout"

const summary: WorkoutSummaryData = {
  id: "w1",
  name: "Push day",
  durationSeconds: 2700,
  setsCompleted: 3,
  volumeKg: 960,
  personalRecords: [],
  nextTargets: [],
  exercises: [
    {
      exerciseId: "bench",
      name: "Bench Press",
      sets: [
        { kind: "warmup", weightKg: 40, reps: 10 },
        { kind: "working", weightKg: 60, reps: 8, rpe: 8.5 },
      ],
    },
    { exerciseId: "dips", name: "Dips", sets: [{ kind: "working", weightKg: 0, reps: 12 }] },
  ],
}

describe("WorkoutSummary", () => {
  it("lists each exercise and its sets in the order they were done", () => {
    render(<WorkoutSummary summary={summary} />, { wrapper: MemoryRouter })
    const done = screen.getByRole("region", { name: "What you did" })
    expect(within(done).getAllByRole("heading").map((heading) => heading.textContent)).toEqual(["What you did", "Bench Press", "Dips"])
    expect(within(done).getByText("Warm-up")).toBeInTheDocument()
    expect(within(done).getByText("RPE 8.5")).toBeInTheDocument()
    expect(within(done).getByText("0 kg × 12")).toBeInTheDocument()
  })

  it("leaves the section out when the server sent no exercises", () => {
    render(<WorkoutSummary summary={{ ...summary, exercises: undefined }} />, { wrapper: MemoryRouter })
    expect(screen.queryByText("What you did")).not.toBeInTheDocument()
  })
})
