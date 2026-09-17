import { format, parseISO } from "date-fns"
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { ChartTooltipBox } from "@/components/charts/chart-tooltip"
import { formatNumber } from "@/lib/format"
import type { WeightPoint } from "@/types/progress"

type WeightChartProps = {
  points: WeightPoint[]
  height?: number
  /** Compact: no axes or grid labels (Home card). */
  compact?: boolean
}

type TooltipPayload = { payload?: WeightPoint }[]

function WeightTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload }) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <ChartTooltipBox
      title={format(parseISO(point.date), "EEE, d MMM")}
      rows={[
        { label: "Scale", value: point.scaleKg == null ? "—" : `${formatNumber(point.scaleKg, 1)} kg`, swatchClassName: "bg-chart-5" },
        { label: "Trend", value: `${formatNumber(point.trendKg, 1)} kg`, swatchClassName: "bg-calories" },
      ]}
    />
  )
}

/** Scale weigh-ins as dots with the smoothed trend line on top. */
export function WeightChart({ points, height = 240, compact = false }: WeightChartProps) {
  // Long ranges: thin the dots so the chart stays readable.
  const showDots = points.length <= 120

  return (
    <div role="img" aria-label={`Scale weight and trend weight, ${points.length} days`} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points} margin={compact ? { top: 6, right: 6, bottom: 0, left: 6 } : { top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis
            dataKey="date"
            hide={compact}
            tickLine={false}
            axisLine={false}
            minTickGap={32}
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            tickFormatter={(value: string) => format(parseISO(value), "d MMM")}
          />
          <YAxis
            hide={compact}
            domain={["dataMin - 0.5", "dataMax + 0.5"]}
            tickLine={false}
            axisLine={false}
            width={48}
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            tickFormatter={(value: number) => formatNumber(value, 1)}
          />
          <Tooltip content={<WeightTooltip />} cursor={{ stroke: "var(--border)" }} />
          <Line
            dataKey="scaleKg"
            name="Scale"
            stroke="none"
            isAnimationActive={false}
            dot={showDots ? { r: 2.5, fill: "var(--chart-5)", stroke: "none" } : false}
            activeDot={{ r: 4, fill: "var(--chart-5)", stroke: "none" }}
          />
          <Line
            dataKey="trendKg"
            name="Trend"
            type="monotone"
            stroke="var(--calories)"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: "var(--calories)", stroke: "var(--background)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function WeightLegend() {
  return (
    <div className="flex items-center gap-4 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span aria-hidden className="size-2 rounded-full bg-chart-5" />
        Scale
      </span>
      <span className="flex items-center gap-1.5">
        <span aria-hidden className="size-2 rounded-full bg-calories" />
        Trend
      </span>
    </div>
  )
}
