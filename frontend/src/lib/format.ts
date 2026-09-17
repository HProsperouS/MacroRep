export function formatNumber(value: number, maximumFractionDigits = 0) {
  return value.toLocaleString("en-SG", { maximumFractionDigits })
}

/** Parses a form value into a number; empty strings become undefined. */
export function toNumber(value: unknown): number | undefined {
  if (value === "" || value === null || value === undefined) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

/** 1934 → "32:14"; 3723 → "1:02:03". */
export function formatDuration(totalSeconds: number) {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  return `${h > 0 ? `${h}:` : ""}${mm}:${String(s).padStart(2, "0")}`
}

/** Signed number with a real minus sign: 4 → "+4", -0.35 → "−0.35". */
export function formatSigned(value: number, maximumFractionDigits = 1) {
  if (value === 0) return "0"
  const text = formatNumber(Math.abs(value), maximumFractionDigits)
  return value > 0 ? `+${text}` : `−${text}`
}

/** Proposal values: kcal without a unit suffix, grams/kg with one. */
export function formatChangeValue(value: number, unit: "kcal" | "g" | "kg") {
  return unit === "kcal" ? formatNumber(value) : `${formatNumber(value, 1)} ${unit}`
}
