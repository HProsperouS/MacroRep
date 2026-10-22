import { addDays, format, isToday, isYesterday, parseISO } from "date-fns"
import { Camera, ChevronLeft, ChevronRight, RotateCw, Search, Zap } from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { apiErrorMessage } from "@/api/client"
import type { UpdateFoodEntryInput } from "@/api/food-api"
import type { CustomFoodSubmit } from "@/components/food/custom-food-form"
import { DailySummaryCard, DailySummarySkeleton } from "@/components/food/daily-summary-card"
import { EditFoodEntryForm } from "@/components/food/edit-food-entry-form"
import { FoodSearchPanel, type FoodSearchPanelProps } from "@/components/food/food-search-panel"
import { ManualEntry, type ManualEntryTab } from "@/components/food/manual-entry"
import { MealSection, MealSectionSkeleton } from "@/components/food/meal-section"
import { PhotoReview } from "@/components/food/photo-review"
import type { QuickAddDraft, QuickAddResult } from "@/components/food/quick-add-form"
import { DayPickerButton } from "@/components/layout/day-picker-button"
import { PageHeader } from "@/components/layout/page-header"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import {
  dateKey,
  useAddFoodEntry,
  useCreateCustomFood,
  useFoodLog,
  useNutritionTargets,
  usePhotoEstimate,
  useRemoveFoodEntry,
  useUpdateFoodEntry,
} from "@/hooks/use-food-log"
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/use-media-query"
import { amountLabelFor } from "@/hooks/use-serving-amount"
import { EMPTY_ENTRIES, groupEntries, mealForTime } from "@/lib/food-log"
import { formatNumber } from "@/lib/format"
import { MEAL_LABELS, MEAL_TYPES, type FoodEntry, type MealType, type PhotoItem } from "@/types/food"

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
  const updateEntry = useUpdateFoodEntry()
  const createCustomFood = useCreateCustomFood()
  const [editing, setEditing] = useState<{ entry: FoodEntry; layout: OverlayLayout } | null>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)
  const [photoLayout, setPhotoLayout] = useState<OverlayLayout | null>(null)
  const photo = usePhotoEstimate()

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

  function scanPhoto() {
    setSearchOpen(false)
    photoInputRef.current?.click()
  }

  function photoChosen(file: File | undefined) {
    if (!file) return
    setPhotoLayout(isDesktop ? "dialog" : "drawer")
    photo.mutate(file)
  }

  async function logPhotoItems(target: MealType, items: PhotoItem[]) {
    let logged = 0
    try {
      for (const item of items) {
        const { name, grams, calories, protein, carbs, fat } = item
        const amountLabel = `${formatNumber(grams, 1)} g · photo estimate`
        await addEntry.mutateAsync({ meal: target, name, amountLabel, source: "photo", calories, protein, carbs, fat })
        logged += 1
      }
      setPhotoLayout(null)
      const total = items.reduce((sum, item) => sum + item.calories, 0)
      toast.success(`Added ${logged} item${logged === 1 ? "" : "s"} to ${MEAL_LABELS[target]}`, { description: `${formatNumber(total)} kcal` })
    } catch (error) {
      toast.error(`Logged ${logged} of ${items.length}; the rest didn’t save`, { description: apiErrorMessage(error) })
    }
    return logged
  }

  function logEntry(entry: Omit<FoodEntry, "id">) {
    setSearchOpen(false)
    addEntry.mutate(entry, {
      onSuccess: () => toast.success(`Added ${entry.name} to ${MEAL_LABELS[entry.meal]}`, { description: `${formatNumber(entry.calories)} kcal` }),
      onError: (error) => toast.error(`Couldn’t add ${entry.name}`, { description: apiErrorMessage(error) }),
    })
  }

  function handleEdit(input: UpdateFoodEntryInput) {
    if (!editing) return
    const { entry } = editing
    updateEntry.mutate(
      { entryId: entry.id, input },
      {
        onSuccess: (updated) => {
          setEditing(null)
          const movedTo = input.date ? ` to ${dayTitle(parseISO(input.date))}` : ""
          toast.success(`Updated ${updated.name}${movedTo}`, { description: `${formatNumber(updated.calories)} kcal` })
        },
        onError: (error) => toast.error(`Couldn’t update ${entry.name}`, { description: apiErrorMessage(error) }),
      },
    )
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
      // Logged as one serving of the saved food, so its amount can be changed later.
      logEntry({
        meal: logTo,
        name: created.name,
        amountLabel: amountLabelFor(created, 1, "serving"),
        source: "custom",
        ...created.nutrition,
        foodId: created.id,
        quantity: 1,
        quantityUnit: "serving",
      })
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
    onScanPhoto: scanPhoto,
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
            <DayPickerButton value={date} max={new Date()} onChange={setDate} />
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
                Search foods and dishes
              </Button>
              <div className="grid grid-cols-2 gap-2">
                <Button variant="outline" className="h-11" onClick={scanPhoto}>
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
                <MealSection
                  key={mealType}
                  meal={mealType}
                  entries={byMeal[mealType]}
                  onAdd={focusSearchFor}
                  onEdit={(entry) => setEditing({ entry, layout: isDesktop ? "dialog" : "drawer" })}
                  onRemove={handleRemove}
                />
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
          <ResponsiveOverlay
            open={searchOpen}
            onOpenChange={setSearchOpen}
            layout="drawer"
            title="Add food"
            description="Search for a food and choose an amount."
            hideDescription
          >
            <FoodSearchPanel {...searchPanelProps} autoFocus />
          </ResponsiveOverlay>
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

      <input
        ref={photoInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        tabIndex={-1}
        aria-label="Meal photo"
        onChange={(event) => {
          photoChosen(event.target.files?.[0])
          event.target.value = "" // so the same photo can be chosen again
        }}
      />

      <ResponsiveOverlay
        open={photoLayout !== null}
        onOpenChange={(open) => (open ? undefined : setPhotoLayout(null))}
        layout={photoLayout ?? "dialog"}
        title="Check the photo estimate"
        description="These are estimates from the photo. Correct anything that's off; nothing is logged until you do."
        dialogClassName="sm:max-w-2xl"
      >
        {photo.isPending ? (
          <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground" role="status">
            <Spinner /> Looking at your meal…
          </p>
        ) : photo.isError ? (
          <div className="flex flex-col items-start gap-3 py-2">
            <p className="text-sm text-destructive" role="alert">
              {apiErrorMessage(photo.error)}
            </p>
            <Button variant="outline" onClick={scanPhoto}>
              Choose another photo
            </Button>
          </div>
        ) : photo.data ? (
          <PhotoReview key={photo.submittedAt} estimate={photo.data} defaultMeal={meal} onLog={logPhotoItems} onRetake={scanPhoto} />
        ) : null}
      </ResponsiveOverlay>

      <ResponsiveOverlay
        open={editing !== null}
        onOpenChange={(open) => (open ? undefined : setEditing(null))}
        layout={editing?.layout ?? "dialog"}
        title="Edit food"
        description={
          editing?.entry.foodId
            ? "Change the amount and the nutrition updates to match. You can also move it to another meal or day."
            : "Adjust the values, or move it to another meal or day."
        }
      >
        {editing ? (
          <EditFoodEntryForm
            key={editing.entry.id}
            entry={editing.entry}
            date={dateKey(date)}
            submitting={updateEntry.isPending}
            onCancel={() => setEditing(null)}
            onSubmit={handleEdit}
          />
        ) : null}
      </ResponsiveOverlay>
    </>
  )
}
