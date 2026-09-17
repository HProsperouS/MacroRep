import { addDays, format, isToday, isYesterday } from "date-fns"
import { Barcode, Camera, ChevronLeft, ChevronRight, RotateCw, Search, Zap } from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import type { CustomFoodSubmit } from "@/components/food/custom-food-form"
import { DailySummaryCard, DailySummarySkeleton } from "@/components/food/daily-summary-card"
import { FoodSearchPanel, type FoodSearchPanelProps } from "@/components/food/food-search-panel"
import { ManualEntry, type ManualEntryTab, type OverlayLayout } from "@/components/food/manual-entry"
import { MealSection, MealSectionSkeleton } from "@/components/food/meal-section"
import type { QuickAddDraft, QuickAddResult } from "@/components/food/quick-add-form"
import { PageHeader } from "@/components/layout/page-header"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer"
import { useAddFoodEntry, useCreateCustomFood, useFoodLog, useNutritionTargets, useRemoveFoodEntry } from "@/hooks/use-food-log"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { EMPTY_ENTRIES, groupEntries, mealForTime } from "@/lib/food-log"
import { formatNumber } from "@/lib/format"
import { MEAL_LABELS, MEAL_TYPES, type FoodEntry, type MealType } from "@/types/food"

type ManualState = {
  open: boolean
  tab: ManualEntryTab
  layout: OverlayLayout
  draft?: QuickAddDraft
  draftKey: number
}

function dayTitle(date: Date) {
  if (isToday(date)) return "Today"
  if (isYesterday(date)) return "Yesterday"
  return format(date, "EEE, d MMM")
}

export default function FoodPage() {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const [date, setDate] = useState(() => new Date())
  const [meal, setMeal] = useState<MealType>(() => mealForTime(new Date()))
  const [searchOpen, setSearchOpen] = useState(false)
  const [manual, setManual] = useState<ManualState>({ open: false, tab: "quick", layout: "dialog", draftKey: 0 })

  const foodLog = useFoodLog(date)
  const targets = useNutritionTargets()
  const addEntry = useAddFoodEntry(date)
  const removeEntry = useRemoveFoodEntry(date)
  const createCustomFood = useCreateCustomFood()

  const entries = foodLog.data?.entries ?? EMPTY_ENTRIES
  const { totals, byMeal } = useMemo(() => groupEntries(entries), [entries])
  const viewingToday = isToday(date)

  function focusSearchFor(target: MealType) {
    setMeal(target)
    if (isDesktop) searchInputRef.current?.focus()
    else setSearchOpen(true)
  }

  function openManual(tab: ManualEntryTab, draft?: QuickAddDraft) {
    setSearchOpen(false)
    setManual((prev) => ({ open: true, tab, draft, draftKey: prev.draftKey + 1, layout: isDesktop ? "dialog" : "drawer" }))
  }

  function notAvailable(feature: string) {
    toast(`${feature} is coming soon`, { description: "It needs the backend image service, which isn’t connected yet." })
  }

  function logEntry(entry: Omit<FoodEntry, "id">) {
    setSearchOpen(false)
    addEntry.mutate(entry, {
      onSuccess: () => toast.success(`Added ${entry.name} to ${MEAL_LABELS[entry.meal]}`, { description: `${formatNumber(entry.calories)} kcal` }),
      onError: (error) => toast.error(`Couldn’t add ${entry.name}`, { description: apiErrorMessage(error) }),
    })
  }

  function handleRemove(entryId: string) {
    removeEntry.mutate(entryId, {
      onError: (error) => toast.error("Couldn’t remove that item", { description: apiErrorMessage(error) }),
    })
  }

  function handleQuickAdd(result: QuickAddResult) {
    setManual((prev) => ({ ...prev, open: false }))
    logEntry({ ...result, amountLabel: "Quick add", source: "quick-add" })
  }

  async function handleCustomSubmit({ food, logTo }: CustomFoodSubmit) {
    try {
      const created = await createCustomFood.mutateAsync(food)
      setManual((prev) => ({ ...prev, open: false }))
      if (logTo) {
        const weight = created.servingWeightG != null && created.servingUnit !== "g" ? ` · ${formatNumber(created.servingWeightG)} g` : ""
        logEntry({
          meal: logTo,
          name: created.name,
          amountLabel: `${formatNumber(created.servingSize, 2)} ${created.servingUnit}${weight}`,
          source: "custom",
          ...created.nutrition,
        })
      } else {
        toast.success(`Saved ${created.name}`, { description: "Find it in search under My food." })
      }
    } catch (error) {
      // The overlay stays open so the user's input isn't lost.
      toast.error("Couldn’t save that food", { description: apiErrorMessage(error) })
    }
  }

  const searchPanelProps: FoodSearchPanelProps = {
    meal,
    onMealChange: setMeal,
    onAdd: logEntry,
    onQuickAdd: () => openManual("quick"),
    onCreateCustom: (name) => openManual("custom", name ? { name } : undefined),
    onUnavailable: notAvailable,
  }

  return (
    <>
      <PageHeader
        eyebrow={format(date, "EEEE, d MMMM")}
        title={dayTitle(date)}
        actions={
          <>
            {viewingToday ? null : (
              <Button variant="ghost" className="hidden h-10 sm:inline-flex" onClick={() => setDate(new Date())}>
                Jump to today
              </Button>
            )}
            <Button variant="outline" size="icon-lg" className="size-10" aria-label="Previous day" onClick={() => setDate((d) => addDays(d, -1))}>
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              size="icon-lg"
              className="size-10"
              aria-label="Next day"
              disabled={viewingToday}
              onClick={() => setDate((d) => addDays(d, 1))}
            >
              <ChevronRight />
            </Button>
          </>
        }
      />

      <div className="grid items-start gap-4 lg:grid-cols-12 lg:gap-6">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-7">
          {foodLog.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Couldn’t load your food log</AlertTitle>
              <AlertDescription>{apiErrorMessage(foodLog.error)}</AlertDescription>
              <AlertAction>
                <Button variant="outline" size="sm" onClick={() => void foodLog.refetch()}>
                  <RotateCw data-icon="inline-start" />
                  Retry
                </Button>
              </AlertAction>
            </Alert>
          ) : null}

          {foodLog.isPending || targets.isPending ? (
            <DailySummarySkeleton />
          ) : targets.data ? (
            <DailySummaryCard totals={totals} targets={targets.data} />
          ) : null}

          {isDesktop ? null : (
            <div className="flex flex-col gap-2">
              <Button variant="outline" className="h-11 justify-start font-normal text-muted-foreground" onClick={() => setSearchOpen(true)}>
                <Search data-icon="inline-start" />
                Search foods, brands, dishes
              </Button>
              <div className="grid grid-cols-3 gap-2">
                <Button variant="outline" className="h-11" onClick={() => notAvailable("Barcode scanning")}>
                  <Barcode data-icon="inline-start" />
                  Barcode
                </Button>
                <Button variant="outline" className="h-11" onClick={() => notAvailable("Meal photo scanning")}>
                  <Camera data-icon="inline-start" />
                  Scan
                </Button>
                <Button variant="outline" className="h-11" onClick={() => openManual("quick")}>
                  <Zap data-icon="inline-start" />
                  Quick add
                </Button>
              </div>
            </div>
          )}

          {foodLog.isPending
            ? MEAL_TYPES.map((mealType) => <MealSectionSkeleton key={mealType} />)
            : MEAL_TYPES.map((mealType) => (
                <MealSection key={mealType} meal={mealType} entries={byMeal[mealType]} onAdd={focusSearchFor} onRemove={handleRemove} />
              ))}
        </div>

        {isDesktop ? (
          <Card className="sticky top-7 lg:col-span-5">
            <CardHeader>
              <CardTitle>Add food</CardTitle>
            </CardHeader>
            <CardContent>
              <FoodSearchPanel {...searchPanelProps} searchInputRef={searchInputRef} />
            </CardContent>
          </Card>
        ) : (
          <Drawer open={searchOpen} onOpenChange={setSearchOpen}>
            <DrawerContent className="max-h-[92dvh]">
              <DrawerHeader className="text-left">
                <DrawerTitle>Add food</DrawerTitle>
                <DrawerDescription className="sr-only">Search for a food and choose an amount.</DrawerDescription>
              </DrawerHeader>
              <div className="overflow-y-auto px-4 pb-6">
                <FoodSearchPanel {...searchPanelProps} autoFocus />
              </div>
            </DrawerContent>
          </Drawer>
        )}
      </div>

      <ManualEntry
        open={manual.open}
        onOpenChange={(open) => setManual((prev) => ({ ...prev, open }))}
        layout={manual.layout}
        tab={manual.tab}
        onTabChange={(tab) => setManual((prev) => ({ ...prev, tab }))}
        defaultMeal={meal}
        targets={targets.data ?? { calories: 0, protein: 0, carbs: 0, fat: 0 }}
        draft={manual.draft}
        draftKey={manual.draftKey}
        onQuickAdd={handleQuickAdd}
        onSaveAsCustom={(draft) => openManual("custom", draft)}
        onCustomSubmit={handleCustomSubmit}
      />
    </>
  )
}
