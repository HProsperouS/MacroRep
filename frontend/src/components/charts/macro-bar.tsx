import { cn } from "@/lib/utils"
import type { Macros } from "@/lib/macros"
import { formatNumber } from "@/lib/format"

export const MACRO_STYLES = {
  protein: { label: "Protein", short: "P", color: "bg-protein" },
  carbs: { label: "Carbs", short: "C", color: "bg-carbs" },
  fat: { label: "Fat", short: "F", color: "bg-fat" },
} as const

export type MacroKey = keyof typeof MACRO_STYLES

type MacroBarProps = {
  macro: MacroKey
  value: number
  target: number
  className?: string
}

export function MacroBar({ macro, value, target, className }: MacroBarProps) {
  const style = MACRO_STYLES[macro]
  const percent = target > 0 ? Math.min(value / target, 1) * 100 : 0
  const rounded = Math.round(value)

  return (
    <div className={cn("flex min-w-0 flex-1 flex-col gap-2", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
          <span className={cn("size-2 rounded-full", style.color)} aria-hidden />
          {style.label}
        </span>
        <span className="text-xs whitespace-nowrap text-muted-foreground">
          <span className="font-display text-base font-semibold text-foreground">{rounded}</span> / {target}g
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={style.label}
        aria-valuemin={0}
        aria-valuemax={target}
        aria-valuenow={rounded}
        className="h-1.5 overflow-hidden rounded-full bg-border"
      >
        <div className={cn("h-full rounded-full transition-[width] duration-500", style.color)} style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

export function MacroInline({ protein, carbs, fat, className }: Macros & { className?: string }) {
  const values: Record<MacroKey, number> = { protein, carbs, fat }
  return (
    <span className={cn("flex items-center gap-2.5 text-xs text-muted-foreground", className)}>
      {(Object.keys(MACRO_STYLES) as MacroKey[]).map((key) => (
        <span key={key} className="flex items-center gap-1">
          <span className={cn("size-1.5 rounded-full", MACRO_STYLES[key].color)} aria-hidden />
          <span>
            {formatNumber(values[key], 1)}
            <span className="sr-only"> g {MACRO_STYLES[key].label}</span>
            <span aria-hidden>{MACRO_STYLES[key].short}</span>
          </span>
        </span>
      ))}
    </span>
  )
}
