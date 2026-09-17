import { RotateCw } from "lucide-react"

import { apiErrorMessage } from "@/api/client"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

type QueryErrorProps = {
  title: string
  error: unknown
  onRetry: () => void
  retrying?: boolean
  className?: string
}

/** Error callout with a Retry action, used when a query fails. */
export function QueryError({ title, error, onRetry, retrying = false, className }: QueryErrorProps) {
  return (
    <Alert variant="destructive" className={className}>
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
          <RotateCw data-icon="inline-start" />
          Retry
        </Button>
      </AlertAction>
    </Alert>
  )
}
