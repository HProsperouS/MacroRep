import { ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"

import { WeightChart, WeightLegend } from "@/components/charts/weight-chart"
import { QueryError } from "@/components/layout/query-error"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatNumber, formatSigned } from "@/lib/format"
import type { ProgressResponse } from "@/types/progress"

type TrendWeightCardProps = {
  data?: ProgressResponse
  error: unknown
  onRetry: () => void
}

export function TrendWeightCard({ data, error, onRetry }: TrendWeightCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trend weight</CardTitle>
        <CardAction>
          <Button variant="link" size="sm" className="px-0" asChild>
            <Link to="/progress">
              View progress
              <ChevronRight data-icon="inline-end" />
            </Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {data ? (
          <>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-4xl leading-none font-semibold">{formatNumber(data.weight.currentTrendKg, 1)}</span>
              <span className="text-sm text-muted-foreground">kg</span>
              <Badge className="ml-auto bg-primary/12 text-primary">{formatSigned(data.weight.ratePerWeekKg, 2)} kg / wk</Badge>
            </div>
            <WeightChart points={data.weight.points} height={96} compact />
            <WeightLegend />
          </>
        ) : error ? (
          <QueryError title="Couldn’t load your weight trend" error={error} onRetry={onRetry} />
        ) : (
          <>
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-24 w-full" />
          </>
        )}
      </CardContent>
    </Card>
  )
}
