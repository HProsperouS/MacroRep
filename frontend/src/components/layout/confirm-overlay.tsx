import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

type ConfirmOverlayProps = {
  /** The layout it was opened with, or null while closed. */
  layout: OverlayLayout | null
  onClose: () => void
  title: string
  description: string
  confirmLabel: string
  cancelLabel?: string
  destructive?: boolean
  pending?: boolean
  onConfirm: () => void
}

/** Asks before something that can't be taken back, with Cancel and a confirm button. */
export function ConfirmOverlay({
  layout,
  onClose,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  destructive = false,
  pending = false,
  onConfirm,
}: ConfirmOverlayProps) {
  return (
    <ResponsiveOverlay
      open={layout !== null}
      // Not closed mid-action (Escape, a click outside): its outcome is shown here.
      onOpenChange={(open) => (open || pending ? undefined : onClose())}
      layout={layout ?? "dialog"}
      title={title}
      description={description}
    >
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="outline" className="h-10" onClick={onClose} disabled={pending}>
          {cancelLabel}
        </Button>
        <Button variant={destructive ? "destructive" : "default"} className="h-10" onClick={onConfirm} disabled={pending}>
          {pending ? <Spinner data-icon="inline-start" /> : null}
          {confirmLabel}
        </Button>
      </div>
    </ResponsiveOverlay>
  )
}
