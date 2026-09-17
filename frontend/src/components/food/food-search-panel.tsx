import { Barcode, Camera, RotateCw, Search, SearchX, Zap } from "lucide-react"
import { useState, type Ref } from "react"

import { MealPicker } from "@/components/food/meal-picker"
import { ServingEditor } from "@/components/food/serving-editor"
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { apiErrorMessage } from "@/api/client"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import { useFoodSearch } from "@/hooks/use-food-log"
import { formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { Food, FoodEntry, MealType } from "@/types/food"

export type FoodSearchPanelProps = {
  meal: MealType
  onMealChange: (meal: MealType) => void
  onAdd: (entry: Omit<FoodEntry, "id">) => void
  onQuickAdd: () => void
  onCreateCustom: (name?: string) => void
  onUnavailable: (feature: string) => void
  searchInputRef?: Ref<HTMLInputElement>
  autoFocus?: boolean
}

function servingLabel(food: Food) {
  const weight = food.servingWeightG != null && food.servingUnit !== "g" ? ` · ${formatNumber(food.servingWeightG)} g` : ""
  return `${formatNumber(food.servingSize, 1)} ${food.servingUnit}${weight}`
}

export function FoodSearchPanel({
  meal,
  onMealChange,
  onAdd,
  onQuickAdd,
  onCreateCustom,
  onUnavailable,
  searchInputRef,
  autoFocus,
}: FoodSearchPanelProps) {
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState<Food | null>(null)
  const debouncedQuery = useDebouncedValue(query.trim(), 250)
  const search = useFoodSearch(debouncedQuery)
  const results = search.data ?? []
  const trimmed = query.trim()
  const settling = trimmed !== debouncedQuery || search.isFetching

  return (
    <div className="flex flex-col gap-4">
      <MealPicker value={meal} onChange={onMealChange} />

      <InputGroup className="h-11">
        <InputGroupAddon>
          <Search />
        </InputGroupAddon>
        <InputGroupInput
          ref={searchInputRef}
          type="search"
          autoFocus={autoFocus}
          autoComplete="off"
          aria-label="Search foods"
          placeholder="Search foods, brands, dishes"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setSelected(null)
          }}
        />
        {settling ? (
          <InputGroupAddon align="inline-end">
            <Spinner />
          </InputGroupAddon>
        ) : null}
      </InputGroup>

      <div className="grid grid-cols-3 gap-2">
        <Button variant="outline" className="h-10" onClick={() => onUnavailable("Barcode scanning")}>
          <Barcode data-icon="inline-start" />
          Barcode
        </Button>
        <Button variant="outline" className="h-10" onClick={() => onUnavailable("Meal photo scanning")}>
          <Camera data-icon="inline-start" />
          Scan
        </Button>
        <Button variant="outline" className="h-10" onClick={onQuickAdd}>
          <Zap data-icon="inline-start" />
          Quick add
        </Button>
      </div>

      <Separator />

      {selected ? (
        <ServingEditor key={selected.id} food={selected} meal={meal} onCancel={() => setSelected(null)} onAdd={onAdd} />
      ) : (
        <SearchResults
          query={trimmed}
          results={results}
          isPending={search.isPending}
          isError={search.isError}
          error={search.error}
          isStale={search.isPlaceholderData}
          onRetry={() => void search.refetch()}
          onSelect={setSelected}
          onQuickAdd={onQuickAdd}
          onCreateCustom={onCreateCustom}
        />
      )}
    </div>
  )
}

type SearchResultsProps = {
  query: string
  results: Food[]
  isPending: boolean
  isError: boolean
  error: unknown
  isStale: boolean
  onRetry: () => void
  onSelect: (food: Food) => void
  onQuickAdd: () => void
  onCreateCustom: (name?: string) => void
}

function SearchResults({ query, results, isPending, isError, error, isStale, onRetry, onSelect, onQuickAdd, onCreateCustom }: SearchResultsProps) {
  if (isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Search isn’t available</AlertTitle>
        <AlertDescription>{apiErrorMessage(error)}</AlertDescription>
        <AlertAction>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCw data-icon="inline-start" />
            Retry
          </Button>
        </AlertAction>
      </Alert>
    )
  }

  if (isPending) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading foods">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <Empty className="border">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <SearchX />
          </EmptyMedia>
          <EmptyTitle>No foods match “{query}”</EmptyTitle>
          <EmptyDescription>Log the numbers once, or save it as your own food to reuse.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent className="flex-row justify-center">
          <Button variant="outline" onClick={onQuickAdd}>
            Quick add
          </Button>
          <Button onClick={() => onCreateCustom(query)}>Create custom food</Button>
        </EmptyContent>
      </Empty>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground" aria-live="polite">
        {query ? `${results.length} result${results.length === 1 ? "" : "s"} for “${query}”` : "Suggestions"}
      </p>
      <ul className={cn("flex flex-col gap-1.5 transition-opacity", isStale && "opacity-60")}>
        {results.map((food) => (
          <li key={food.id}>
            <button
              type="button"
              onClick={() => onSelect(food)}
              className="flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors outline-none hover:bg-muted/50 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-medium">{food.name}</span>
                  {food.source === "custom" ? <Badge variant="secondary">My food</Badge> : null}
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  {food.brand ? `${food.brand} · ` : ""}
                  {servingLabel(food)}
                </span>
              </span>
              <span className="shrink-0 whitespace-nowrap">
                <span className="font-display text-lg font-semibold">{formatNumber(food.nutrition.calories)}</span>{" "}
                <span className="text-xs text-muted-foreground">kcal</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
