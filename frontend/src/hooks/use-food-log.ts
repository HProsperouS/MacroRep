import { format } from "date-fns"
import { useCallback, useState } from "react"

import { SAMPLE_ENTRIES } from "@/data/sample-food"
import type { Food, FoodEntry } from "@/types/food"

export function dateKey(date: Date) {
  return format(date, "yyyy-MM-dd")
}

const withId = <T extends object>(item: T) => ({ ...item, id: crypto.randomUUID() })

/**
 * In-memory food log seeded with sample data.
 * Swap the internals for TanStack Query queries/mutations once the API exists —
 * the returned shape can stay the same so pages don't change.
 */
export function useFoodLog() {
  const [entriesByDate, setEntriesByDate] = useState<Record<string, FoodEntry[]>>(() => ({
    [dateKey(new Date())]: SAMPLE_ENTRIES.map(withId),
  }))
  const [customFoods, setCustomFoods] = useState<Food[]>([])

  const getEntries = useCallback((date: Date) => entriesByDate[dateKey(date)] ?? [], [entriesByDate])

  const addEntry = useCallback((date: Date, entry: Omit<FoodEntry, "id">) => {
    const key = dateKey(date)
    setEntriesByDate((prev) => ({ ...prev, [key]: [...(prev[key] ?? []), withId(entry)] }))
  }, [])

  const removeEntry = useCallback((date: Date, entryId: string) => {
    const key = dateKey(date)
    setEntriesByDate((prev) => ({ ...prev, [key]: (prev[key] ?? []).filter((entry) => entry.id !== entryId) }))
  }, [])

  const addCustomFood = useCallback((food: Omit<Food, "id" | "source">) => {
    const created: Food = { ...food, id: crypto.randomUUID(), source: "custom" }
    setCustomFoods((prev) => [created, ...prev])
    return created
  }, [])

  return { getEntries, addEntry, removeEntry, customFoods, addCustomFood }
}
