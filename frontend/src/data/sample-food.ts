import type { DailyTargets, Food, FoodEntry } from "@/types/food"

/**
 * Sample data for building the UI before the FastAPI backend exists.
 * Replace with TanStack Query calls to /api/foods and /api/food-log.
 */

export const SAMPLE_TARGETS: DailyTargets = {
  calories: 2350,
  protein: 165,
  carbs: 250,
  fat: 70,
}

export const SAMPLE_FOODS: Food[] = [
  { id: "f-salmon", name: "Salmon fillet, baked", servingSize: 100, servingUnit: "g", servingWeightG: 100, nutrition: { calories: 206, protein: 22.6, carbs: 0, fat: 12.4 }, source: "database" },
  { id: "f-salmon-sashimi", name: "Salmon sashimi", servingSize: 100, servingUnit: "g", servingWeightG: 100, nutrition: { calories: 179, protein: 20, carbs: 0, fat: 11 }, source: "database" },
  { id: "f-chicken-rice", name: "Chicken rice bowl", servingSize: 1, servingUnit: "bowl", servingWeightG: 380, nutrition: { calories: 520, protein: 42, carbs: 58, fat: 12 }, source: "database" },
  { id: "f-brown-rice", name: "Brown rice, cooked", servingSize: 100, servingUnit: "g", servingWeightG: 100, nutrition: { calories: 122, protein: 2.7, carbs: 25.6, fat: 1 }, source: "database" },
  { id: "f-broccoli", name: "Broccoli, steamed", servingSize: 100, servingUnit: "g", servingWeightG: 100, nutrition: { calories: 35, protein: 2.4, carbs: 7, fat: 0.4 }, source: "database" },
  { id: "f-banana", name: "Banana", servingSize: 1, servingUnit: "piece", servingWeightG: 118, nutrition: { calories: 105, protein: 1.3, carbs: 27, fat: 0.4 }, source: "database" },
  { id: "f-greek-yogurt", name: "Greek yogurt, 0% fat", servingSize: 170, servingUnit: "g", servingWeightG: 170, nutrition: { calories: 100, protein: 17, carbs: 6, fat: 0.7 }, source: "database" },
  { id: "f-whey", name: "Whey protein", brand: "Generic", servingSize: 1, servingUnit: "scoop", servingWeightG: 30, nutrition: { calories: 120, protein: 24, carbs: 3, fat: 1.5 }, source: "database" },
  { id: "f-kopi-o", name: "Kopi-o kosong", servingSize: 1, servingUnit: "cup", nutrition: { calories: 5, protein: 0.3, carbs: 0.5, fat: 0 }, source: "database" },
  { id: "f-olive-oil", name: "Olive oil", servingSize: 1, servingUnit: "tbsp", servingWeightG: 13.5, nutrition: { calories: 119, protein: 0, carbs: 0, fat: 13.5 }, source: "database" },
  { id: "f-egg", name: "Egg, boiled", servingSize: 1, servingUnit: "piece", servingWeightG: 50, nutrition: { calories: 78, protein: 6.3, carbs: 0.6, fat: 5.3 }, source: "database" },
  { id: "f-oats", name: "Rolled oats", servingSize: 40, servingUnit: "g", servingWeightG: 40, nutrition: { calories: 150, protein: 5, carbs: 27, fat: 2.6 }, source: "database" },
  { id: "f-kaya-toast", name: "Kaya toast", servingSize: 2, servingUnit: "slice", servingWeightG: 70, nutrition: { calories: 260, protein: 5, carbs: 34, fat: 11 }, source: "database" },
  { id: "f-fish-soup", name: "Sliced fish soup", servingSize: 1, servingUnit: "bowl", servingWeightG: 550, nutrition: { calories: 320, protein: 34, carbs: 12, fat: 14 }, source: "database" },
]

export const SAMPLE_ENTRIES: Omit<FoodEntry, "id">[] = [
  { meal: "lunch", name: "Chicken rice bowl", amountLabel: "1 bowl · 380 g", calories: 520, protein: 42, carbs: 58, fat: 12, source: "database" },
  { meal: "lunch", name: "Kopi-o kosong", amountLabel: "1 cup", calories: 5, protein: 0.3, carbs: 0.5, fat: 0, source: "database" },
  { meal: "lunch", name: "Banana", amountLabel: "1 piece · 118 g", calories: 105, protein: 1.3, carbs: 27, fat: 0.4, source: "database" },
  { meal: "dinner", name: "Salmon fillet, baked", amountLabel: "150 g", calories: 309, protein: 33.9, carbs: 0, fat: 18.6, source: "database" },
  { meal: "dinner", name: "Brown rice, cooked", amountLabel: "180 g", calories: 220, protein: 4.9, carbs: 46.1, fat: 1.8, source: "database" },
  { meal: "dinner", name: "Broccoli, steamed", amountLabel: "120 g", calories: 42, protein: 2.9, carbs: 8.4, fat: 0.5, source: "database" },
  { meal: "snacks", name: "Greek yogurt, 0% fat", amountLabel: "170 g", calories: 100, protein: 17, carbs: 6, fat: 0.7, source: "database" },
  { meal: "snacks", name: "Whey protein", amountLabel: "1 scoop · 30 g", calories: 120, protein: 24, carbs: 3, fat: 1.5, source: "database" },
]
