import { Plus, Zap } from "lucide-react"

import { CustomFoodForm, type CustomFoodSubmit } from "@/components/food/custom-food-form"
import { QuickAddForm, type QuickAddDraft, type QuickAddResult } from "@/components/food/quick-add-form"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import type { DailyTargets, MealType } from "@/types/food"

export type ManualEntryTab = "quick" | "custom"
export type OverlayLayout = "dialog" | "drawer"

type ManualEntryProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Chosen when the overlay opens, so resizing mid-entry never remounts the form. */
  layout: OverlayLayout
  tab: ManualEntryTab
  onTabChange: (tab: ManualEntryTab) => void
  defaultMeal: MealType
  targets: DailyTargets
  draft?: QuickAddDraft
  /** Changes whenever a new draft is handed over, to reset the custom form. */
  draftKey: number
  onQuickAdd: (result: QuickAddResult) => void
  onSaveAsCustom: (draft: QuickAddDraft) => void
  onCustomSubmit: (result: CustomFoodSubmit) => Promise<void>
}

const TITLE = "Add food manually"
const DESCRIPTION = "Quick add logs numbers once. A custom food is saved with a serving size so you can reuse it."

export function ManualEntry({ open, onOpenChange, layout, ...bodyProps }: ManualEntryProps) {
  if (layout === "drawer") {
    return (
      <Drawer open={open} onOpenChange={onOpenChange}>
        <DrawerContent className="max-h-[92dvh]">
          <DrawerHeader className="text-left">
            <DrawerTitle>{TITLE}</DrawerTitle>
            <DrawerDescription>{DESCRIPTION}</DrawerDescription>
          </DrawerHeader>
          <div className="overflow-y-auto px-4 pb-6">
            <ManualEntryBody {...bodyProps} />
          </div>
        </DrawerContent>
      </Drawer>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("max-h-[90dvh] overflow-y-auto sm:p-6", bodyProps.tab === "custom" ? "sm:max-w-5xl" : "sm:max-w-xl")}>
        <DialogHeader>
          <DialogTitle>{TITLE}</DialogTitle>
          <DialogDescription>{DESCRIPTION}</DialogDescription>
        </DialogHeader>
        <ManualEntryBody {...bodyProps} />
      </DialogContent>
    </Dialog>
  )
}

type ManualEntryBodyProps = Omit<ManualEntryProps, "open" | "onOpenChange" | "layout">

function ManualEntryBody({ tab, onTabChange, defaultMeal, targets, draft, draftKey, onQuickAdd, onSaveAsCustom, onCustomSubmit }: ManualEntryBodyProps) {
  return (
    <Tabs value={tab} onValueChange={(value) => onTabChange(value as ManualEntryTab)} className="gap-5">
      <TabsList className="w-full sm:w-fit">
        <TabsTrigger value="quick" className="px-3">
          <Zap data-icon="inline-start" />
          Quick add
        </TabsTrigger>
        <TabsTrigger value="custom" className="px-3">
          <Plus data-icon="inline-start" />
          Custom food
        </TabsTrigger>
      </TabsList>
      <TabsContent value="quick">
        <QuickAddForm defaultMeal={defaultMeal} onSubmit={onQuickAdd} onSaveAsCustom={onSaveAsCustom} />
      </TabsContent>
      <TabsContent value="custom">
        <CustomFoodForm key={draftKey} defaultMeal={defaultMeal} draft={draft} targets={targets} onSubmit={onCustomSubmit} />
      </TabsContent>
    </Tabs>
  )
}
