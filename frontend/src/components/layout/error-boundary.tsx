import { TriangleAlert } from "lucide-react"
import { Component, type ErrorInfo, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { cn } from "@/lib/utils"

type ErrorBoundaryProps = {
  children: ReactNode
  /** Centred on the whole screen, for when there's no app shell around it. */
  fullScreen?: boolean
}

type ErrorBoundaryState = { error: Error | null }

/**
 * Catches an error while rendering what's inside, so one broken page shows a way out instead of a
 * blank app. Also catches a page whose code fails to load (e.g. after a new release), which a reload
 * fixes. Errors in event handlers and requests don't reach it: those are shown where they happen.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("A page failed to render", error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className={cn("flex flex-1 items-center justify-center", this.props.fullScreen && "min-h-dvh bg-background px-4")}>
        <Empty className="max-w-md border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <TriangleAlert />
            </EmptyMedia>
            <EmptyTitle>Something went wrong on this page</EmptyTitle>
            <EmptyDescription>Your data is safe. Try again, or reload if it keeps happening.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent className="flex-row justify-center">
            <Button variant="outline" onClick={() => this.setState({ error: null })}>
              Try again
            </Button>
            <Button onClick={() => window.location.reload()}>Reload</Button>
          </EmptyContent>
        </Empty>
      </div>
    )
  }
}
