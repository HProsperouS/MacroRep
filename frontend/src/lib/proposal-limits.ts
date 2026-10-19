import { formatChangeValue } from "@/lib/format"
import type { ProposalChange } from "@/types/coach"

/**
 * How far an edited value may move from the current one, per unit. Mirrors the
 * backend's limits (`app/coach/agents/limits.py`), so an edit the server would
 * refuse is caught here first.
 */
const LIMITS: Record<ProposalChange["unit"], { share?: number; by?: number; min: number; max: number; whole?: boolean }> = {
  kcal: { share: 0.25, min: 1, max: 10_000 },
  g: { share: 0.25, min: 1, max: 1_000 },
  kg: { share: 0.1, min: 0, max: 1_000 },
  sets: { by: 1, min: 1, max: 10, whole: true },
  reps: { by: 3, min: 1, max: 30, whole: true },
}

/** Why `raw` can't be applied for `change`, or undefined when it can. */
export function editedValueError(change: ProposalChange, raw: string): string | undefined {
  const trimmed = raw.trim()
  const value = Number(trimmed)
  if (trimmed === "" || !Number.isFinite(value)) return "Enter a number"
  const limit = LIMITS[change.unit]
  if (limit.whole && !Number.isInteger(value)) return "Enter a whole number"
  if (value < limit.min) return limit.min > 0 ? `Must be at least ${limit.min}` : "Can’t be negative"
  if (value > limit.max) return `Must be ${limit.max.toLocaleString("en-SG")} or less`
  const room = limit.by ?? change.before * (limit.share ?? 0)
  if (Math.abs(value - change.before) > room + 1e-9) {
    return limit.by !== undefined
      ? `Change it by at most ${limit.by} from ${formatChangeValue(change.before, change.unit)}`
      : `Stay within ${Math.round((limit.share ?? 0) * 100)}% of ${formatChangeValue(change.before, change.unit)}`
  }
  return undefined
}
