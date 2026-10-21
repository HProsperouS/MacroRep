import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { EXPERIENCE_LEVEL_LABELS, EXPERIENCE_LEVELS, GOAL_LABELS, GOALS, type ExperienceLevel, type Goal } from "@/types/profile"
import { EQUIPMENT, EQUIPMENT_LABELS, type Equipment } from "@/types/workout"

type ChoiceProps<T> = {
  /** Undefined until one is chosen (nothing shows as selected). */
  value: T | undefined
  onChange: (value: T) => void
  disabled?: boolean
}

/** One of a few options, side by side; clicking the chosen one again keeps it chosen. */
function SingleChoice<T extends string>({ options, labels, label, value, onChange, disabled }: ChoiceProps<T> & { options: readonly T[]; labels: Record<T, string>; label: string }) {
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      spacing={0}
      value={value ?? ""}
      onValueChange={(next) => (next ? onChange(next as T) : undefined)}
      aria-label={label}
      className="w-full"
      disabled={disabled}
    >
      {options.map((option) => (
        <ToggleGroupItem key={option} value={option} className="h-10 flex-1">
          {labels[option]}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

export function GoalChoice(props: ChoiceProps<Goal>) {
  return <SingleChoice options={GOALS} labels={GOAL_LABELS} label="Goal" {...props} />
}

export function ExperienceChoice(props: ChoiceProps<ExperienceLevel>) {
  return <SingleChoice options={EXPERIENCE_LEVELS} labels={EXPERIENCE_LEVEL_LABELS} label="Training experience" {...props} />
}

export function EquipmentChoice({ value, onChange, disabled }: { value: Equipment[]; onChange: (value: Equipment[]) => void; disabled?: boolean }) {
  return (
    <ToggleGroup type="multiple" variant="outline" value={value} onValueChange={(next: Equipment[]) => onChange(next)} aria-label="Available equipment" className="flex-wrap" disabled={disabled}>
      {EQUIPMENT.map((item) => (
        <ToggleGroupItem key={item} value={item} className="h-10 data-[state=on]:border-primary/45 data-[state=on]:bg-primary/7">
          {EQUIPMENT_LABELS[item]}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}
