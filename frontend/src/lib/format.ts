export function formatNumber(value: number, maximumFractionDigits = 0) {
  return value.toLocaleString("en-SG", { maximumFractionDigits })
}

/** Parses a form value into a number; empty strings become undefined. */
export function toNumber(value: unknown): number | undefined {
  if (value === "" || value === null || value === undefined) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}
