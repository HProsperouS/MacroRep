import { describe, expect, it } from "vitest"

import { formatChangeValue, formatDuration, formatSigned, toNumber } from "@/lib/format"

describe("format", () => {
  it("formats durations with and without hours", () => {
    expect(formatDuration(1934)).toBe("32:14")
    expect(formatDuration(3723)).toBe("1:02:03")
    expect(formatDuration(-5)).toBe("0:00")
  })

  it("signs numbers with a real minus", () => {
    expect(formatSigned(4)).toBe("+4")
    expect(formatSigned(-0.35, 2)).toBe("−0.35")
    expect(formatSigned(-0.35)).toBe("−0.4")
    expect(formatSigned(0)).toBe("0")
  })

  it("parses form values, leaving blank and junk undefined", () => {
    expect(toNumber("12.5")).toBe(12.5)
    expect(toNumber("")).toBeUndefined()
    expect(toNumber("abc")).toBeUndefined()
  })

  it("shows calories bare and grams or kilograms with their unit", () => {
    expect(formatChangeValue(2400, "kcal")).toBe("2,400")
    expect(formatChangeValue(180, "g")).toBe("180 g")
    expect(formatChangeValue(82.55, "kg")).toBe("82.6 kg")
    expect(formatChangeValue(4, "sets")).toBe("4 sets")
    expect(formatChangeValue(8, "reps")).toBe("8 reps")
  })
})
