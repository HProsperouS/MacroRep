export type Macros = {
  protein: number
  carbs: number
  fat: number
}

export type Nutrition = Macros & {
  calories: number
}

/** Energy from macros using Atwater factors (4 / 4 / 9 kcal per gram). */
export function caloriesFromMacros({ protein, carbs, fat }: Macros) {
  return Math.round(protein * 4 + carbs * 4 + fat * 9)
}

/** True when entered calories differ from the macro total by more than `tolerance` (default 5%). */
export function caloriesMismatch(calories: number, macros: Macros, tolerance = 0.05) {
  const computed = caloriesFromMacros(macros)
  if (computed === 0) return false
  return Math.abs(calories - computed) / computed > tolerance
}

export function sumNutrition(items: Nutrition[]): Nutrition {
  return items.reduce(
    (total, item) => ({
      calories: total.calories + item.calories,
      protein: total.protein + item.protein,
      carbs: total.carbs + item.carbs,
      fat: total.fat + item.fat,
    }),
    { calories: 0, protein: 0, carbs: 0, fat: 0 },
  )
}

export function scaleNutrition(nutrition: Nutrition, factor: number): Nutrition {
  const round1 = (value: number) => Math.round(value * factor * 10) / 10
  return {
    calories: Math.round(nutrition.calories * factor),
    protein: round1(nutrition.protein),
    carbs: round1(nutrition.carbs),
    fat: round1(nutrition.fat),
  }
}

/** Share of energy from each macro, as whole percentages. */
export function energySplit(macros: Macros) {
  const total = caloriesFromMacros(macros)
  if (total === 0) return { protein: 0, carbs: 0, fat: 0 }
  return {
    protein: Math.round(((macros.protein * 4) / total) * 100),
    carbs: Math.round(((macros.carbs * 4) / total) * 100),
    fat: Math.round(((macros.fat * 9) / total) * 100),
  }
}
