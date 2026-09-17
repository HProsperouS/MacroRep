import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

type StatProps = {
  label: string
  value: ReactNode
  unit?: string
  hint?: ReactNode
  className?: string
}

/** Label over a large condensed number, with an optional unit and hint line. */
export function Stat({ label, value, unit, hint, className }: StatProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <span className="text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">{label}</span>
      <span className="flex items-baseline gap-1.5">
        <span className="font-display text-3xl leading-none font-semibold">{value}</span>
        {unit ? <span className="text-sm text-muted-foreground">{unit}</span> : null}
      </span>
      {hint ? <span className="truncate text-xs text-muted-foreground">{hint}</span> : null}
    </div>
  )
}
