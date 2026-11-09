import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { FindWeightHint } from "@/components/workout/find-weight-hint"
import type { SessionExercise, SessionSet } from "@/lib/workout-session"

function exercise(sets: Partial<SessionSet>[], finding = true): SessionExercise {
  return {
    id: "squat",
    exerciseId: "squat",
    name: "Squat",
    equipment: "Barbell",
    muscles: "Quads",
    restSeconds: 90,
    finding,
    sets: sets.map((set, index) => ({
      id: `s${index}`,
      kind: "working",
      weight: "",
      reps: "8",
      rpe: "",
      done: false,
      ...set,
    })),
  }
}

describe("FindWeightHint", () => {
  it("tells a first-time lifter to start light and rate the set by RPE", () => {
    render(<FindWeightHint exercise={exercise([{}, {}])} />)
    expect(screen.getByText(/find your weight by feel/i)).toBeInTheDocument()
    expect(screen.getByText(/about 3 more reps than the 8 planned/i)).toBeInTheDocument()
    expect(screen.getByText(/10 means nothing left/i)).toBeInTheDocument()
  })

  it("asks for an RPE after a set without one", () => {
    render(<FindWeightHint exercise={exercise([{ weight: "40", done: true }, {}])} />)
    expect(screen.getByText(/enter an rpe for the set you just did/i)).toBeInTheDocument()
  })

  it("says whether to go up or down after a rated set", () => {
    render(<FindWeightHint exercise={exercise([{ weight: "40", rpe: "9", done: true }, {}])} />)
    expect(screen.getByText("RPE 9 was close to your limit. Try 37.5 kg.")).toBeInTheDocument()
    expect(screen.getByText(/trust how the set felt/i)).toBeInTheDocument()
  })

  it("stays out of the way for an exercise with a weight to follow", () => {
    const { container } = render(<FindWeightHint exercise={exercise([{ weight: "60" }], false)} />)
    expect(container).toBeEmptyDOMElement()
  })

  it("stays out of the way for a bodyweight set", () => {
    const { container } = render(<FindWeightHint exercise={exercise([{ weight: "0", rpe: "7", done: true }])} />)
    expect(container).toBeEmptyDOMElement()
  })
})
