import { Check, CircleAlert, Clock, LoaderCircle } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { PipelineStep, PipelineStepStatus } from "@/types/coach"

const STATUS: Record<PipelineStepStatus, { label: string; icon: typeof Check; className: string }> = {
  done: { label: "Done", icon: Check, className: "bg-primary text-primary-foreground" },
  running: { label: "In progress", icon: LoaderCircle, className: "bg-muted text-foreground [&_svg]:animate-spin" },
  waiting: { label: "Waiting for you", icon: Clock, className: "bg-carbs/15 text-carbs" },
  failed: { label: "Failed", icon: CircleAlert, className: "bg-destructive/15 text-destructive" },
}

/** How the check-in was produced: data → agents → reviewer → user. */
export function PipelineSteps({ steps }: { steps: PipelineStep[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>How this check-in was made</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="grid gap-3 md:grid-cols-5 md:gap-4">
          {steps.map((step) => {
            const status = STATUS[step.status]
            const Icon = status.icon
            return (
              <li key={step.id} className="flex min-w-0 items-start gap-3 md:flex-col md:gap-2">
                <span className={cn("flex size-7 shrink-0 items-center justify-center rounded-full", status.className)}>
                  <Icon className="size-4" aria-hidden />
                  <span className="sr-only">{status.label}</span>
                </span>
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-medium">{step.title}</span>
                  <span className="text-xs text-muted-foreground">{step.detail}</span>
                </span>
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}
