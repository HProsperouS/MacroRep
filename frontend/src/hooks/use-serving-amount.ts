import { useState } from "react"

import { formatNumber, toNumber } from "@/lib/format"
import { scaleNutrition, type Nutrition } from "@/lib/macros"
import type { Food, QuantityUnit } from "@/types/food"

export const MAX_AMOUNT = 5000

export type ServingAmount = {
  unit: QuantityUnit
  /** The raw input text. */
  amount: string
  setAmount: (amount: string) => void
  changeUnit: (unit: QuantityUnit) => void
  /** The parsed amount, when the input is a valid number in range. */
  value: number | undefined
  /** Preview of the nutrition for this amount; the server computes the logged values the same way. */
  scaled: Nutrition | null
}

/** Amount + unit state for logging a food. Mount the consumer with `key={food.id}` to reset per food. */
export function useServingAmount(food: Food, initial?: { quantity: number; unit: QuantityUnit }): ServingAmount {
  const byWeightOnly = food.servingUnit === "g"
  const [unit, setUnit] = useState<QuantityUnit>(initial?.unit ?? (byWeightOnly ? "g" : "serving"))
  const [amount, setAmount] = useState(() => (initial ? String(initial.quantity) : byWeightOnly ? String(food.servingSize) : "1"))

  const parsed = toNumber(amount)
  const value = parsed !== undefined && parsed > 0 && parsed <= MAX_AMOUNT ? parsed : undefined
  const scaled = value !== undefined ? scaleNutrition(food.nutrition, unit === "g" ? value / (food.servingWeightG ?? food.servingSize) : value) : null

  function changeUnit(next: QuantityUnit) {
    if (next === unit) return
    setAmount(next === "g" ? String(food.servingWeightG ?? 100) : "1")
    setUnit(next)
  }

  return { unit, amount, setAmount, changeUnit, value, scaled }
}

/** Mirrors the label the server stores, for the optimistic row shown while saving. */
export function amountLabelFor(food: Food, quantity: number, unit: QuantityUnit) {
  if (unit === "g") return `${formatNumber(quantity, 1)} g`
  const weight = food.servingWeightG && food.servingUnit !== "g" ? ` · ${formatNumber(quantity * food.servingWeightG)} g` : ""
  return `${formatNumber(quantity * food.servingSize, 1)} ${food.servingUnit}${weight}`
}
