import { Trash2 } from "lucide-react"

import { MacroInline } from "@/components/charts/macro-bar"
import { Button } from "@/components/ui/button"
import { formatNumber } from "@/lib/format"
import type { FoodEntry } from "@/types/food"

type FoodRowProps = {
  entry: FoodEntry
  onEdit: (entry: FoodEntry) => void
  onRemove: (entryId: string) => void
}

export function FoodRow({ entry, onEdit, onRemove }: FoodRowProps) {
  const pending = entry.id.startsWith("optimistic-")

  return (
    <li className="group flex items-center gap-1 pr-2 transition-colors hover:bg-muted/50" aria-busy={pending || undefined}>
      <button
        type="button"
        className="flex min-w-0 flex-1 items-center gap-3 py-2.5 pl-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset disabled:cursor-default"
        aria-label={`Edit ${entry.name}`}
        disabled={pending}
        onClick={() => onEdit(entry)}
      >
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="truncate text-sm font-medium">{entry.name}</span>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="truncate text-xs text-muted-foreground">{entry.amountLabel}</span>
            <MacroInline protein={entry.protein} carbs={entry.carbs} fat={entry.fat} />
          </span>
        </span>
        <span className="shrink-0 whitespace-nowrap">
          <span className="font-display text-lg font-semibold">{formatNumber(entry.calories)}</span>{" "}
          <span className="text-xs text-muted-foreground">kcal</span>
        </span>
      </button>
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
