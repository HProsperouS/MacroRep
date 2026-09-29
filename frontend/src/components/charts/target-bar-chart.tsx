import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { ChartTooltipBox } from "@/components/charts/chart-tooltip"

export type TargetBarDatum = {
  key: string
  label: string
  tooltipTitle: string
  value: number
  /** Draws the bar faded, e.g. a day that may not be fully logged. */
  muted?: boolean
  /** Shown in the tooltip under the values. */
  note?: string
}

type TargetBarChartProps = {
  data: TargetBarDatum[]
  target: number
  /** What the dashed line represents, e.g. "Target" or "Average". */
  targetLabel?: string
  seriesLabel: string
  formatValue: (value: number) => string
  ariaLabel: string
  height?: number
}


/** Bars against a dashed reference line — weekly volume and daily calories. */
export function TargetBarChart({ data, target, targetLabel = "Target", seriesLabel, formatValue, ariaLabel, height = 220 }: TargetBarChartProps) {
  const max = Math.max(target, ...data.map((d) => d.value))

  return (
    <div role="img" aria-label={ariaLabel} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={8} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
          <YAxis
            domain={[0, Math.ceil(max * 1.1)]}
            tickLine={false}
            axisLine={false}
            width={48}
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            tickFormatter={(value: number) => formatValue(value)}
          />
          <Tooltip
            content={({ active, payload }) => {
              const datum = payload?.[0]?.payload as TargetBarDatum | undefined
              if (!active || !datum) return null
              return (
                <ChartTooltipBox
                  title={datum.tooltipTitle}
                  rows={[
                    { label: seriesLabel, value: formatValue(datum.value), swatchClassName: "bg-protein" },
                    { label: targetLabel, value: formatValue(target), swatchClassName: "bg-muted-foreground" },
                  ]}
                  note={datum.note}
                />
              )
            }} cursor={{ fill: "var(--muted)", opacity: 0.5 }} />
          <ReferenceLine y={target} stroke="var(--muted-foreground)" strokeDasharray="4 4" />
          <Bar dataKey="value" name={seriesLabel} fill="var(--protein)" radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false}>
            {data.map((datum) => (
              <Cell key={datum.key} fillOpacity={datum.muted ? 0.4 : 1} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
