import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { z } from "zod"

import type { UpdateFoodEntryInput } from "@/api/food-api"
import { TextField } from "@/components/food/form-field"
import { MealPicker } from "@/components/food/meal-picker"
import { AmountFields, NutrientTiles } from "@/components/food/serving-editor"
import { QueryError } from "@/components/layout/query-error"
import { Button } from "@/components/ui/button"
import { FieldGroup, FieldLegend, FieldSet } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { useFood } from "@/hooks/use-food-log"
import { useServingAmount } from "@/hooks/use-serving-amount"
import { isLoggableDay, toDayKey } from "@/lib/dates"
import { toNumber } from "@/lib/format"
import { MEAL_TYPES, type Food, type FoodEntry, type MealType } from "@/types/food"

type EditFoodEntryFormProps = {
  entry: FoodEntry
  /** The day the entry is currently logged on, yyyy-MM-dd. */
  date: string
  submitting: boolean
  onCancel: () => void
  /** Called with only the fields that changed. */
  onSubmit: (input: UpdateFoodEntryInput) => void
}

/**
 * A saved food's entry is edited by amount (nutrition re-scales from the food); a quick add
 * by its values. Either can move to another meal or day.
 */
export function EditFoodEntryForm(props: EditFoodEntryFormProps) {
  return props.entry.foodId ? <SavedFoodLoader {...props} foodId={props.entry.foodId} /> : <EnteredValuesForm {...props} />
}

function SavedFoodLoader({ foodId, ...props }: EditFoodEntryFormProps & { foodId: string }) {
  const food = useFood(foodId)
  if (food.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading food">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }
  if (food.isError) {
    return <QueryError title="Couldn’t load this food" error={food.error} onRetry={() => void food.refetch()} retrying={food.isFetching} />
  }
  return <SavedFoodForm key={food.data.id} food={food.data} {...props} />
}

function SavedFoodForm({ entry, food, date, submitting, onCancel, onSubmit }: EditFoodEntryFormProps & { food: Food }) {
  const [meal, setMeal] = useState<MealType>(entry.meal)
  const [day, setDay] = useState(date)
  const amount = useServingAmount(food, entry.quantity != null ? { quantity: entry.quantity, unit: entry.quantityUnit ?? "serving" } : undefined)

  const dayValid = isLoggableDay(day)
  const changes: UpdateFoodEntryInput = {
    ...(meal !== entry.meal && { meal }),
    ...(day !== date && { date: day }),
    ...(amount.value !== undefined && amount.value !== entry.quantity && { quantity: amount.value }),
    ...(amount.unit !== entry.quantityUnit && { quantityUnit: amount.unit }),
  }
  const canSave = dayValid && amount.value !== undefined && Object.keys(changes).length > 0

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={(event) => {
        event.preventDefault()
        if (canSave) onSubmit(changes)
      }}
    >
      <FieldGroup>
        <p className="truncate text-base font-medium">{food.name}</p>
        <MealAndDay meal={meal} onMealChange={setMeal} day={day} onDayChange={setDay} dayError={dayValid ? undefined : DAY_ERROR} disabled={submitting} />
        <AmountFields food={food} amount={amount} idPrefix="edit-entry" />
        <NutrientTiles nutrition={amount.scaled} />
      </FieldGroup>
      <FormActions submitting={submitting} canSave={canSave} onCancel={onCancel} />
    </form>
  )
}

const DAY_ERROR = "Pick today or an earlier day"

const toNumberOrNaN = (value: unknown) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN)

const numberField = (max: number, { integer = false } = {}) => {
  const base = z
    .number({ required_error: "Enter a value", invalid_type_error: "Enter a number" })
    .min(0, "Can’t be negative")
    .max(max, "That looks too high")
  return z.preprocess(toNumberOrNaN, integer ? base.int("Use a whole number") : base)
}

const enteredValuesSchema = z.object({
  meal: z.enum(MEAL_TYPES),
  day: z.string().refine(isLoggableDay, DAY_ERROR),
  name: z.string().trim().min(1, "Enter a name").max(255, "Keep it under 255 characters"),
  calories: numberField(10_000, { integer: true }),
  protein: numberField(1_000),
  carbs: numberField(1_000),
  fat: numberField(1_000),
})

type EnteredValuesInput = z.input<typeof enteredValuesSchema>
type EnteredValuesValues = z.output<typeof enteredValuesSchema>

function EnteredValuesForm({ entry, date, submitting, onCancel, onSubmit }: EditFoodEntryFormProps) {
  const {
    control,
    register,
    handleSubmit,
    setValue,
    formState: { errors, isDirty },
  } = useForm<EnteredValuesInput, unknown, EnteredValuesValues>({
    resolver: zodResolver(enteredValuesSchema),
    defaultValues: {
      meal: entry.meal,
      day: date,
      name: entry.name,
      calories: String(entry.calories),
      protein: String(entry.protein),
      carbs: String(entry.carbs),
      fat: String(entry.fat),
    },
  })

  const [meal, day] = useWatch({ control, name: ["meal", "day"] })

  const submit = handleSubmit((values) => {
    onSubmit({
      ...(values.meal !== entry.meal && { meal: values.meal }),
      ...(values.day !== date && { date: values.day }),
      ...(values.name !== entry.name && { name: values.name }),
      ...(values.calories !== entry.calories && { calories: values.calories }),
      ...(values.protein !== entry.protein && { protein: values.protein }),
      ...(values.carbs !== entry.carbs && { carbs: values.carbs }),
      ...(values.fat !== entry.fat && { fat: values.fat }),
    })
  })

  return (
    <form noValidate className="flex flex-col gap-5" onSubmit={submit}>
      <FieldGroup>
        <MealAndDay
          meal={meal}
          onMealChange={(next) => setValue("meal", next, { shouldDirty: true })}
          day={day}
          onDayChange={(next) => setValue("day", next, { shouldDirty: true, shouldValidate: true })}
          dayError={errors.day?.message}
          disabled={submitting}
        />
        <TextField id="edit-entry-name" label="Name" error={errors.name?.message} disabled={submitting} {...register("name")} />
        <TextField
          id="edit-entry-calories"
          label="Calories"
          unit="kcal"
          inputMode="numeric"
          dotClassName="bg-calories"
          error={errors.calories?.message}
          disabled={submitting}
          {...register("calories")}
        />
        <div className="grid grid-cols-3 gap-3">
          <TextField id="edit-entry-protein" label="Protein" unit="g" inputMode="decimal" dotClassName="bg-protein" error={errors.protein?.message} disabled={submitting} {...register("protein")} />
          <TextField id="edit-entry-carbs" label="Carbs" unit="g" inputMode="decimal" dotClassName="bg-carbs" error={errors.carbs?.message} disabled={submitting} {...register("carbs")} />
          <TextField id="edit-entry-fat" label="Fat" unit="g" inputMode="decimal" dotClassName="bg-fat" error={errors.fat?.message} disabled={submitting} {...register("fat")} />
        </div>
      </FieldGroup>
      <FormActions submitting={submitting} canSave={isDirty} onCancel={onCancel} />
    </form>
  )
}

type MealAndDayProps = {
  meal: MealType
  onMealChange: (meal: MealType) => void
  day: string
  onDayChange: (day: string) => void
  dayError?: string
  disabled: boolean
}

function MealAndDay({ meal, onMealChange, day, onDayChange, dayError, disabled }: MealAndDayProps) {
  return (
    <>
      <FieldSet className="gap-2">
        <FieldLegend variant="label">Meal</FieldLegend>
        <MealPicker value={meal} onChange={onMealChange} />
      </FieldSet>
      <TextField
        id="edit-entry-day"
        label="Day"
        type="date"
        max={toDayKey(new Date())}
        value={day}
        onChange={(event) => onDayChange(event.target.value)}
        error={dayError}
        disabled={disabled}
      />
    </>
  )
}

function FormActions({ submitting, canSave, onCancel }: { submitting: boolean; canSave: boolean; onCancel: () => void }) {
  return (
    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={submitting}>
        Cancel
      </Button>
      <Button type="submit" className="h-10" disabled={submitting || !canSave}>
        {submitting ? <Spinner data-icon="inline-start" /> : null}
        Save changes
      </Button>
    </div>
  )
}
