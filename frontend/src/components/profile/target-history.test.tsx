import { act, renderHook, screen, waitFor, within } from "@testing-library/react"
import { QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { TargetHistory } from "@/components/profile/target-history"
import { useUpdateTargets } from "@/hooks/use-profile"
import { renderWithQuery } from "@/test/render"
import type { TargetVersion } from "@/types/food"

const api = vi.hoisted(() => ({ getTargetHistory: vi.fn(), updateTargets: vi.fn() }))
vi.mock("@/api/profile-api", () => ({ profileApi: api }))

const history: TargetVersion[] = [
  { version: 3, calories: 2100, protein: 160, carbs: 220, fat: 65, effectiveDate: "2026-10-19", source: "check-in", changedAt: "2026-10-19T09:00:00Z" },
  { version: 2, calories: 2000, protein: 160, carbs: 220, fat: 65, effectiveDate: "2026-10-01", source: "manual", changedAt: "2026-10-01T09:00:00Z" },
  { version: 1, calories: 2200, protein: 150, carbs: 230, fat: 70, effectiveDate: "2026-09-15", source: "initial", changedAt: "2026-09-15T09:00:00Z" },
]

beforeEach(() => {
  api.getTargetHistory.mockResolvedValue(history)
})

describe("TargetHistory", () => {
  it("lists every version newest first, with when it applied from and where it came from", async () => {
    renderWithQuery(<TargetHistory />)
    const items = within(await screen.findByRole("list", { name: "Target history" })).getAllByRole("listitem")

    expect(items).toHaveLength(3)
    expect(items[0]).toHaveTextContent("2,100 kcal")
    expect(items[0]).toHaveTextContent("Current")
    expect(items[0]).toHaveTextContent("From 19 Oct 2026")
    expect(items[0]).toHaveTextContent("From a check-in")
    expect(items[1]).toHaveTextContent("Set by you")
    expect(items[1]).not.toHaveTextContent("Current")
    expect(items[2]).toHaveTextContent("Starting targets")
    expect(items[2]).toHaveTextContent("P 150 g · C 230 g · F 70 g")
  })

  it("offers a retry when the history can't load", async () => {
    api.getTargetHistory.mockRejectedValue(new Error("offline"))
    renderWithQuery(<TargetHistory />)
    expect(await screen.findByText("Couldn’t load the target history")).toBeInTheDocument()
  })

  it("refreshes after the targets are saved", async () => {
    api.updateTargets.mockImplementation(async (input) => input)
    const { queryClient } = renderWithQuery(<TargetHistory />)
    await screen.findByRole("list", { name: "Target history" })
    expect(api.getTargetHistory).toHaveBeenCalledTimes(1)

    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useUpdateTargets(), { wrapper })
    await act(() => result.current.mutateAsync({ calories: 2300, protein: 160, carbs: 220, fat: 65 }))

    await waitFor(() => expect(api.getTargetHistory).toHaveBeenCalledTimes(2))
  })
})
