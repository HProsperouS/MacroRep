import { describe, expect, it } from "vitest"

import { caloriesFromMacros, caloriesImplausiblyLow, caloriesMismatch, energySplit, scaleNutrition } from "@/lib/macros"

const macros = { protein: 150, carbs: 250, fat: 70 } // 600 + 1000 + 630 = 2230 kcal

describe("macros", () => {
  it("converts macros to calories with Atwater factors", () => {
    expect(caloriesFromMacros(macros)).toBe(2230)
  })

  it("flags calories that disagree with the macros by more than 5%", () => {
    expect(caloriesMismatch(2300, macros)).toBe(false)
    expect(caloriesMismatch(2600, macros)).toBe(true)
    expect(caloriesMismatch(100, { protein: 0, carbs: 0, fat: 0 })).toBe(false)
  })

  it("mirrors the server's rule: only calories under half the macros' total are implausible", () => {
    expect(caloriesImplausiblyLow(1100, macros)).toBe(true)
    expect(caloriesImplausiblyLow(1115, macros)).toBe(false)
    expect(caloriesImplausiblyLow(3000, macros)).toBe(false) // alcohol has energy but no macros
    expect(caloriesImplausiblyLow(1, { protein: 5, carbs: 5, fat: 0 })).toBe(false) // under 50 kcal isn't judged
  })

  it("scales a serving", () => {
    expect(scaleNutrition({ calories: 100, protein: 10, carbs: 5.5, fat: 2 }, 1.5)).toEqual({ calories: 150, protein: 15, carbs: 8.3, fat: 3 })
  })

  it("splits energy into whole percentages", () => {
    expect(energySplit(macros)).toEqual({ protein: 27, carbs: 45, fat: 28 })
    expect(energySplit({ protein: 0, carbs: 0, fat: 0 })).toEqual({ protein: 0, carbs: 0, fat: 0 })
  })
})
