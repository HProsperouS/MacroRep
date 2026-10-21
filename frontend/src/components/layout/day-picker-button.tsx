import { CalendarDays } from "lucide-react"
import { useRef } from "react"

import { Button } from "@/components/ui/button"
import { toDayKey } from "@/lib/dates"

type DayPickerButtonProps = {
  value: Date
  /** The latest day that can be picked; days after it can't be. */
  max: Date
  onChange: (day: Date) => void
}

/**
 * A calendar button that opens the browser's own date picker: the native one on phones,
 * with nothing to add to the bundle. The input sits under the button, so the picker
 * opens beside it.
 */
export function DayPickerButton({ value, max, onChange }: DayPickerButtonProps) {
  const input = useRef<HTMLInputElement>(null)

  function open() {
    const field = input.current
    if (!field) return
    // showPicker isn't in every browser (nor in jsdom); focusing still lets the keyboard pick a day.
    if (typeof field.showPicker === "function") field.showPicker()
    else field.focus()
  }

  return (
    <span className="relative inline-flex">
      <Button variant="outline" size="icon-lg" className="size-10" aria-label="Choose a day" onClick={open}>
        <CalendarDays />
      </Button>
      <input
        ref={input}
        type="date"
        aria-label="Day"
        tabIndex={-1}
        className="pointer-events-none absolute inset-0 opacity-0"
        value={toDayKey(value)}
        max={toDayKey(max)}
        onChange={(event) => {
          const [year, month, day] = event.target.value.split("-").map(Number)
          // Cleared, or a day past the limit typed in: nothing to go to.
          if (!year || event.target.value > toDayKey(max)) return
          onChange(new Date(year, month - 1, day))
        }}
      />
    </span>
  )
}
