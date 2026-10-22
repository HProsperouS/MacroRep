import type { ReactNode } from "react"

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer"
import { cn } from "@/lib/utils"

export type OverlayLayout = "dialog" | "drawer"

type ResponsiveOverlayProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Chosen by the caller when opening, so resizing mid-edit never remounts the content. */
  layout: OverlayLayout
  title: string
  description: string
  hideDescription?: boolean
  /** The dialog's classes, e.g. a wider max width; the drawer always spans the screen. */
  dialogClassName?: string
  children: ReactNode
}

/** Dialog at ≥1024px, bottom drawer below (handoff §7). */
export function ResponsiveOverlay({ open, onOpenChange, layout, title, description, hideDescription = false, dialogClassName, children }: ResponsiveOverlayProps) {
  if (layout === "drawer") {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent>
          <DrawerHeader className="text-left">
            <DrawerTitle>{title}</DrawerTitle>
            <DrawerDescription className={cn(hideDescription && "sr-only")}>{description}</DrawerDescription>
          </DrawerHeader>
          <div className="overflow-y-auto px-4 pb-6">{children}</div>
        </DrawerContent>
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* The title and close button stay put; only the body scrolls when it's taller than the screen. */}
      <DialogContent className={cn("flex flex-col overflow-hidden sm:max-w-md", dialogClassName)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className={cn(hideDescription && "sr-only")}>{description}</DialogDescription>
        </DialogHeader>
        {/* Bleeds into the padding, so focus rings at the edges aren't cut off. */}
        <div className="-mx-4 -mb-4 min-h-0 overflow-y-auto px-4 pb-4">{children}</div>
      </DialogContent>
    </Dialog>
  )
}
