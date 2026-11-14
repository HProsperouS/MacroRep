import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { StrengthList } from "@/components/progress/strength-list"

describe("StrengthList", () => {
  it("lists band exercises by their best reps under the 1RM lifts", () => {
    render(
      <StrengthList
        lifts={[{ exercise: "Push-Up", estimated1RmKg: 93.3, changeKg: 2 }]}
        repLifts={[{ exercise: "Resistance Band Pull-Apart", bestReps: 25, changeReps: 3 }]}
      />,
    )
    expect(screen.getByText("Push-Up")).toBeInTheDocument()
    const bands = screen.getByRole("region", { name: "Best set, reps (bands)" })
    expect(within(bands).getByText("Resistance Band Pull-Apart").closest("li")).toHaveTextContent("25reps+3")
  })

  it("asks for sets when there is nothing yet", () => {
    render(<StrengthList lifts={[]} repLifts={[]} />)
    expect(screen.getByText(/Log a few working sets/)).toBeInTheDocument()
  })
})
