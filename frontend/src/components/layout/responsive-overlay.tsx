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
  className?: string
  children: ReactNode
}

/** Dialog at ≥1024px, bottom drawer below (handoff §7). */
export function ResponsiveOverlay({ open, onOpenChange, layout, title, description, hideDescription = false, className, children }: ResponsiveOverlayProps) {
  if (layout === "drawer") {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent className="max-h-[92dvh]">
          <DrawerHeader className="text-left">
            <DrawerTitle>{title}</DrawerTitle>
            <DrawerDescription className={cn(hideDescription && "sr-only")}>{description}</DrawerDescription>
          </DrawerHeader>
          <div className={cn("overflow-y-auto px-4 pb-6", className)}>{children}</div>
        </DrawerContent>
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("sm:max-w-md", className)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className={cn(hideDescription && "sr-only")}>{description}</DialogDescription>
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  )
}
