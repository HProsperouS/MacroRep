import { Trash2 } from "lucide-react"

import { MacroInline } from "@/components/charts/macro-bar"
import { Button } from "@/components/ui/button"
import { formatNumber } from "@/lib/format"
import type { FoodEntry } from "@/types/food"

type FoodRowProps = {
  entry: FoodEntry
  onRemove: (entryId: string) => void
}

export function FoodRow({ entry, onRemove }: FoodRowProps) {
  const pending = entry.id.startsWith("optimistic-")

  return (
    <li className="group flex items-center gap-3 py-2.5 pr-2 pl-4 transition-colors hover:bg-muted/50" aria-busy={pending || undefined}>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="truncate text-sm font-medium">{entry.name}</span>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="truncate text-xs text-muted-foreground">{entry.amountLabel}</span>
          <MacroInline protein={entry.protein} carbs={entry.carbs} fat={entry.fat} />
        </div>
      </div>
      <span className="shrink-0 whitespace-nowrap">
        <span className="font-display text-lg font-semibold">{formatNumber(entry.calories)}</span>{" "}
        <span className="text-xs text-muted-foreground">kcal</span>
      </span>
      <Button
        variant="ghost"
        size="icon-lg"
        className="text-muted-foreground lg:opacity-0 lg:group-hover:opacity-100 lg:focus-visible:opacity-100"
        aria-label={`Remove ${entry.name}`}
        disabled={pending}
        onClick={() => onRemove(entry.id)}
      >
        <Trash2 />
      </Button>
    </li>
  )
}
