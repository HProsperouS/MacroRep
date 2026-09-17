import type { ReactNode } from "react"

type ChartTooltipBoxProps = {
  title: string
  rows: { label: string; value: string; swatchClassName: string }[]
}

/** Tooltip body shared by the Recharts charts; styled with theme tokens. */
export function ChartTooltipBox({ title, rows }: ChartTooltipBoxProps): ReactNode {
  return (
    <div className="flex min-w-32 flex-col gap-1.5 rounded-lg border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <span className="font-medium">{title}</span>
      {rows.map((row) => (
        <span key={row.label} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <span aria-hidden className={`size-2 rounded-full ${row.swatchClassName}`} />
            {row.label}
          </span>
          <span className="font-medium tabular-nums">{row.value}</span>
        </span>
      ))}
    </div>
  )
}
