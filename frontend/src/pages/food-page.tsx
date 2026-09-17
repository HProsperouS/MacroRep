import { addDays, format, isToday, isYesterday } from "date-fns"
import { Barcode, Camera, ChevronLeft, ChevronRight, Search, Zap } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { DailySummaryCard } from "@/components/food/daily-summary-card"
import { FoodSearchPanel } from "@/components/food/food-search-panel"
import { ManualEntry, type ManualEntryTab } from "@/components/food/manual-entry"
import { MealSection } from "@/components/food/meal-section"
import type { CustomFoodSubmit } from "@/components/food/custom-food-form"
import type { QuickAddDraft, QuickAddResult } from "@/components/food/quick-add-form"
import { PageHeader } from "@/components/layout/page-header"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { SAMPLE_FOODS, SAMPLE_TARGETS } from "@/data/sample-food"
import { useFoodLog } from "@/hooks/use-food-log"
import { formatNumber } from "@/lib/format"
import { sumNutrition } from "@/lib/macros"
import { MEAL_LABELS, MEAL_TYPES, type FoodEntry, type MealType } from "@/types/food"

function mealForTime(date: Date): MealType {
  const hour = date.getHours()
  if (hour < 10) return "breakfast"
  if (hour < 15) return "lunch"
  if (hour < 21) return "dinner"
  return "snacks"
}

function dayTitle(date: Date) {
  if (isToday(date)) return "Today"
  if (isYesterday(date)) return "Yesterday"
  return format(date, "EEE, d MMM")
}

export default function FoodPage() {
  const log = useFoodLog()
  const [date, setDate] = useState(() => new Date())
  const [meal, setMeal] = useState<MealType>(() => mealForTime(new Date()))
  const [searchOpen, setSearchOpen] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [manualTab, setManualTab] = useState<ManualEntryTab>("quick")
  const [draft, setDraft] = useState<QuickAddDraft>()
  const [draftKey, setDraftKey] = useState(0)

  const entries = log.getEntries(date)
  const totals = useMemo(() => sumNutrition(entries), [entries])
  const foods = useMemo(() => [...log.customFoods, ...SAMPLE_FOODS], [log.customFoods])
  const viewingToday = isToday(date)

  function addForMeal(target: MealType) {
    setMeal(target)
    if (window.matchMedia("(min-width: 1024px)").matches) {
      document.getElementById("food-search")?.focus()
    } else {
      setSearchOpen(true)
    }
  }

  function openManual(tab: ManualEntryTab, nextDraft?: QuickAddDraft) {
    setSearchOpen(false)
    setDraft(nextDraft)
    setDraftKey((key) => key + 1)
    setManualTab(tab)
    setManualOpen(true)
  }

  function notAvailable(feature: string) {
    toast(`${feature} is coming soon`, { description: "It needs the backend image service, which isn’t connected yet." })
  }

  function handleAdd(entry: Omit<FoodEntry, "id">) {
    log.addEntry(date, entry)
    setSearchOpen(false)
    toast.success(`Added ${entry.name} to ${MEAL_LABELS[entry.meal]}`, { description: `${formatNumber(entry.calories)} kcal` })
  }

  function handleQuickAdd(result: QuickAddResult) {
    handleAdd({ ...result, amountLabel: "Quick add", source: "quick-add" })
    setManualOpen(false)
  }

  function handleCustomSubmit({ food, logTo }: CustomFoodSubmit) {
    const created = log.addCustomFood(food)
    setManualOpen(false)
    if (logTo) {
      const weight = created.servingWeightG && created.servingUnit !== "g" ? ` · ${formatNumber(created.servingWeightG)} g` : ""
      handleAdd({
        meal: logTo,
        name: created.name,
        amountLabel: `${formatNumber(created.servingSize, 2)} ${created.servingUnit}${weight}`,
        source: "custom",
        ...created.nutrition,
      })
    } else {
      toast.success(`Saved ${created.name}`, { description: "Find it in search under My food." })
    }
  }

  const searchPanelProps = {
    foods,
    meal,
    onMealChange: setMeal,
    onAdd: handleAdd,
    onQuickAdd: () => openManual("quick"),
    onCreateCustom: (name?: string) => openManual("custom", name ? { name } : undefined),
    onUnavailable: notAvailable,
  }

  return (
    <>
      <PageHeader
        eyebrow={format(date, "EEEE, d MMMM")}
        title={dayTitle(date)}
        actions={
          <>
            {!viewingToday && (
              <Button variant="ghost" className="hidden h-11 sm:inline-flex" onClick={() => setDate(new Date())}>
                Jump to today
              </Button>
            )}
            <Button variant="outline" size="icon" className="size-11" aria-label="Previous day" onClick={() => setDate((d) => addDays(d, -1))}>
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="size-11"
              aria-label="Next day"
              disabled={viewingToday}
              onClick={() => setDate((d) => addDays(d, 1))}
            >
              <ChevronRight />
            </Button>
          </>
        }
      />

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-5">
        <div className="flex flex-col gap-4 lg:col-span-7">
          <DailySummaryCard totals={totals} targets={SAMPLE_TARGETS} />

          {/* Mobile + tablet log actions; desktop uses the side panel */}
          <div className="flex flex-col gap-2 lg:hidden">
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="flex h-12 items-center gap-3 rounded-xl border bg-secondary px-3.5 text-left text-base text-muted-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <Search className="size-5" aria-hidden />
              Search foods, brands, dishes
            </button>
            <div className="grid grid-cols-3 gap-2">
              <Button variant="outline" className="h-16 flex-col gap-1 rounded-xl text-xs" onClick={() => notAvailable("Barcode scanning")}>
                <Barcode className="size-5" /> Barcode
              </Button>
              <Button variant="outline" className="h-16 flex-col gap-1 rounded-xl text-xs" onClick={() => notAvailable("Meal photo scanning")}>
                <Camera className="size-5" /> Scan meal
              </Button>
              <Button variant="outline" className="h-16 flex-col gap-1 rounded-xl text-xs" onClick={() => openManual("quick")}>
                <Zap className="size-5" /> Quick add
              </Button>
            </div>
          </div>

          {MEAL_TYPES.map((mealType) => (
            <MealSection
              key={mealType}
              meal={mealType}
              entries={entries.filter((entry) => entry.meal === mealType)}
              onAdd={addForMeal}
              onRemove={(id) => log.removeEntry(date, id)}
            />
          ))}
        </div>

        <aside className="sticky top-7 hidden lg:col-span-5 lg:block">
          <FoodSearchPanel {...searchPanelProps} />
        </aside>
      </div>

      {/* Search sheet for smaller screens */}
      <Sheet open={searchOpen} onOpenChange={setSearchOpen}>
        <SheetContent side="bottom" className="max-h-[92dvh] gap-0 overflow-y-auto rounded-t-3xl border-t bg-card px-0 pt-3 pb-6 lg:hidden">
          <div className="mx-auto mb-1 h-1.5 w-10 rounded-full bg-muted-foreground/30" aria-hidden />
          <SheetHeader className="sr-only">
            <SheetTitle>Add food</SheetTitle>
            <SheetDescription>Search for a food and choose an amount.</SheetDescription>
          </SheetHeader>
          <FoodSearchPanel {...searchPanelProps} autoFocus className="border-0 bg-transparent" />
        </SheetContent>
      </Sheet>

      <ManualEntry
        open={manualOpen}
        onOpenChange={setManualOpen}
        tab={manualTab}
        onTabChange={setManualTab}
        defaultMeal={meal}
        targets={SAMPLE_TARGETS}
        draft={draft}
        draftKey={draftKey}
        onQuickAdd={handleQuickAdd}
        onSaveAsCustom={(nextDraft) => openManual("custom", nextDraft)}
        onCustomSubmit={handleCustomSubmit}
      />
    </>
  )
}
