import { describe, expect, it } from "vitest"

import { rangeError, rangeFor } from "@/lib/history-range"

const today = new Date(2026, 10, 13) // 13 Nov 2026, local time

describe("rangeFor", () => {
  it.each([
    ["all", {}],
    ["today", { from: "2026-11-13", to: "2026-11-13" }],
    ["week", { from: "2026-11-07", to: "2026-11-13" }],
    ["month", { from: "2026-10-15", to: "2026-11-13" }],
  ] as const)("covers %s", (preset, expected) => {
    expect(rangeFor(preset, today)).toEqual(expected)
  })

  it("keeps only the real dates of a custom range", () => {
    expect(rangeFor("custom", today, { from: "2026-10-01", to: "2026-10-31" })).toEqual({ from: "2026-10-01", to: "2026-10-31" })
    expect(rangeFor("custom", today, { from: "2026-02-30", to: "soon" })).toEqual({})
    expect(rangeFor("custom", today, { to: "2026-10-31" })).toEqual({ to: "2026-10-31" })
  })

  it("flags a range that ends before it starts", () => {
    expect(rangeError({ from: "2026-10-31", to: "2026-10-01" })).toMatch(/after the end/)
    expect(rangeError({ from: "2026-10-01", to: "2026-10-01" })).toBeNull()
    expect(rangeError({ from: "2026-10-01" })).toBeNull()
  })
})
