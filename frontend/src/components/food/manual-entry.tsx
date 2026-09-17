import { Plus, Zap } from "lucide-react"
import type { ReactNode } from "react"

import { CustomFoodForm, type CustomFoodSubmit } from "@/components/food/custom-food-form"
import { QuickAddForm, type QuickAddDraft, type QuickAddResult } from "@/components/food/quick-add-form"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useIsMobile } from "@/hooks/use-mobile"
import { cn } from "@/lib/utils"
import type { DailyTargets, MealType } from "@/types/food"

export type ManualEntryTab = "quick" | "custom"

type ManualEntryProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  tab: ManualEntryTab
  onTabChange: (tab: ManualEntryTab) => void
  defaultMeal: MealType
  targets: DailyTargets
  draft?: QuickAddDraft
  /** Changes whenever a new draft is handed over, to reset the custom form. */
  draftKey: number
  onQuickAdd: (result: QuickAddResult) => void
  onSaveAsCustom: (draft: QuickAddDraft) => void
  onCustomSubmit: (result: CustomFoodSubmit) => void
}

const TITLE = "Add food manually"
const DESCRIPTION = "Quick add logs numbers once. A custom food is saved with a serving size so you can reuse it."

/** Quick add + custom food. Bottom sheet on mobile, dialog on desktop. */
export function ManualEntry(props: ManualEntryProps) {
  const { open, onOpenChange, tab } = props
  const isMobile = useIsMobile()
  const body = <ManualEntryBody {...props} />

  if (isMobile) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="bottom" className="max-h-[92dvh] gap-0 overflow-y-auto rounded-t-3xl border-t bg-card px-4 pt-3 pb-8">
          <div className="mx-auto mb-2 h-1.5 w-10 rounded-full bg-muted-foreground/30" aria-hidden />
          <SheetHeader className="px-0 pt-1 pb-4">
            <SheetTitle className="text-xl font-semibold">{TITLE}</SheetTitle>
            <SheetDescription>{DESCRIPTION}</SheetDescription>
          </SheetHeader>
          {body}
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "max-h-[90dvh] gap-0 overflow-y-auto rounded-2xl bg-card p-6 transition-[max-width]",
          tab === "custom" ? "sm:max-w-5xl" : "sm:max-w-xl",
        )}
      >
        <DialogHeader className="pb-5">
          <DialogTitle className="text-xl font-semibold">{TITLE}</DialogTitle>
          <DialogDescription>{DESCRIPTION}</DialogDescription>
        </DialogHeader>
        {body}
      </DialogContent>
    </Dialog>
  )
}

function ManualEntryBody({
  tab,
  onTabChange,
  defaultMeal,
  targets,
  draft,
  draftKey,
  onQuickAdd,
  onSaveAsCustom,
  onCustomSubmit,
}: ManualEntryProps) {
  return (
    <Tabs value={tab} onValueChange={(value) => onTabChange(value as ManualEntryTab)} className="gap-5">
      <TabsList className="h-11! w-full sm:w-fit">
        <TabTrigger value="quick" icon={<Zap />}>
          Quick add
        </TabTrigger>
        <TabTrigger value="custom" icon={<Plus />}>
          Custom food
        </TabTrigger>
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

function TabTrigger({ value, icon, children }: { value: ManualEntryTab; icon: ReactNode; children: ReactNode }) {
  return (
    <TabsTrigger value={value} className="px-4 text-sm">
      {icon}
      {children}
    </TabsTrigger>
  )
}
