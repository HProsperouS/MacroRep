import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  ACTIVITY_LEVEL_LABELS,
  ACTIVITY_LEVELS,
  EXPERIENCE_LEVEL_LABELS,
  EXPERIENCE_LEVELS,
  GOAL_LABELS,
  GOALS,
  SEX_LABELS,
  SEXES,
  type ActivityLevel,
  type ExperienceLevel,
  type Goal,
  type Sex,
} from "@/types/profile"
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

export function SexChoice(props: ChoiceProps<Sex>) {
  return <SingleChoice options={SEXES} labels={SEX_LABELS} label="Sex" {...props} />
}

/** Four long options: a list rather than buttons side by side. */
export function ActivityChoice({ id, value, onChange, disabled }: ChoiceProps<ActivityLevel> & { id: string }) {
  return (
    <Select value={value ?? ""} onValueChange={(next) => onChange(next as ActivityLevel)} disabled={disabled}>
      <SelectTrigger id={id} className="h-10 w-full" aria-label="Activity level">
        <SelectValue placeholder="Choose your activity level" />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {ACTIVITY_LEVELS.map((level) => (
            <SelectItem key={level} value={level}>
              {ACTIVITY_LEVEL_LABELS[level]}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
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
