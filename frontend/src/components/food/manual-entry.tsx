import { Plus, Zap } from "lucide-react"

import { CustomFoodForm, type CustomFoodSubmit } from "@/components/food/custom-food-form"
import { QuickAddForm, type QuickAddDraft, type QuickAddResult } from "@/components/food/quick-add-form"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { DailyTargets, MealType } from "@/types/food"

export type ManualEntryTab = "quick" | "custom"

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
  return (
    <ResponsiveOverlay
      open={open}
      onOpenChange={onOpenChange}
      layout={layout}
      title={TITLE}
      description={DESCRIPTION}
      dialogClassName={bodyProps.tab === "custom" ? "sm:max-w-5xl" : "sm:max-w-xl"}
    >
      <ManualEntryBody {...bodyProps} />
    </ResponsiveOverlay>
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
