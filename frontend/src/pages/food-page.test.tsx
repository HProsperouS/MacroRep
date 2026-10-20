import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import FoodPage from "@/pages/food-page"
import { renderWithQuery } from "@/test/render"
import type { Food, FoodEntry } from "@/types/food"

const api = vi.hoisted(() => ({
  getFoodLog: vi.fn(),
  addEntry: vi.fn(),
  updateEntry: vi.fn(),
  removeEntry: vi.fn(),
  searchFoods: vi.fn(),
  getFood: vi.fn(),
  createCustomFood: vi.fn(),
  getTargets: vi.fn(),
}))
vi.mock("@/api/food-api", () => ({ foodApi: api }))
vi.mock("@/hooks/use-media-query", () => ({ DESKTOP_QUERY: "(min-width: 1024px)", useMediaQuery: () => true }))

const chicken: Food = {
  id: "f-chicken",
  name: "Chicken breast",
  servingSize: 100,
  servingUnit: "g",
  servingWeightG: 100,
  nutrition: { calories: 165, protein: 31, carbs: 0, fat: 3.6 },
  source: "database",
}

const rice: FoodEntry = {
  id: "e-rice",
  meal: "lunch",
  name: "Chicken rice",
  amountLabel: "1 plate",
  source: "quick-add",
  calories: 600,
  protein: 25,
  carbs: 80,
  fat: 20,
}

const today = "2026-10-20"

function mealCard(name: string) {
  return screen.getByText(name, { selector: "[data-slot=card-title]" }).closest<HTMLElement>("[data-slot=card]")!
}

beforeEach(() => {
  // Noon, so "today" can't change part way through a test.
  vi.useFakeTimers({ toFake: ["Date"] })
  vi.setSystemTime(new Date(2026, 9, 20, 12, 0))
  api.getFoodLog.mockImplementation((date: string) => Promise.resolve({ date, entries: date === today ? [rice] : [] }))
  api.getTargets.mockResolvedValue({ calories: 2200, protein: 150, carbs: 250, fat: 70 })
  api.searchFoods.mockResolvedValue([chicken])
})

afterEach(() => {
  vi.useRealTimers()
})

describe("FoodPage", () => {
  it("shows the day's entries by meal against the targets", async () => {
    renderWithQuery(<FoodPage />)

    expect(await screen.findByText("Chicken rice")).toBeInTheDocument()
    expect(screen.getByText("/ 2,200 kcal")).toBeInTheDocument()
    expect(screen.getByText("1,600 kcal left")).toBeInTheDocument()
    expect(within(mealCard("Lunch")).getByText("600 kcal · 1 item")).toBeInTheDocument()
    expect(within(mealCard("Dinner")).getByText("Not logged")).toBeInTheDocument()
  })

  it("moves between days, but not past today", async () => {
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    expect(screen.getByRole("button", { name: "Next day" })).toBeDisabled()
    await user.click(screen.getByRole("button", { name: "Previous day" }))

    expect(screen.getByRole("heading", { name: "Yesterday" })).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText("Chicken rice")).not.toBeInTheDocument())
    expect(api.getFoodLog).toHaveBeenLastCalledWith("2026-10-19", expect.anything())

    await user.click(screen.getByRole("button", { name: "Jump to today" }))
    expect(await screen.findByText("Chicken rice")).toBeInTheDocument()
  })

  it("searches, picks an amount and logs a saved food to the chosen meal", async () => {
    api.addEntry.mockImplementation((input) => Promise.resolve({ ...input, id: "e-new", name: "Chicken breast", amountLabel: "200 g", source: "database", calories: 330, protein: 62, carbs: 0, fat: 7.2 }))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Add food to Dinner" }))
    await user.type(screen.getByRole("searchbox", { name: "Search foods" }), "chicken")
    await user.click(await screen.findByRole("button", { name: /Chicken breast/ }))

    const editor = screen.getByRole("region", { name: "Amount of Chicken breast" })
    await user.clear(within(editor).getByLabelText("Amount"))
    await user.type(within(editor).getByLabelText("Amount"), "200")
    expect(within(editor).getByText("330")).toBeInTheDocument()
    await user.click(within(editor).getByRole("button", { name: "Add to Dinner" }))

    await waitFor(() =>
      expect(api.addEntry).toHaveBeenCalledWith({ date: today, meal: "dinner", foodId: "f-chicken", quantity: 200, quantityUnit: "g" }),
    )
    expect(toast.success).toHaveBeenCalledWith("Added Chicken breast to Dinner", { description: "330 kcal" })
  })

  it("offers quick add and a custom food when a search finds nothing", async () => {
    api.searchFoods.mockResolvedValue([])
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.type(screen.getByRole("searchbox", { name: "Search foods" }), "laksa")
    expect(await screen.findByText("No foods match “laksa”")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Create custom food" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    expect(within(dialog).getByLabelText("Food name")).toHaveValue("laksa")
  })

  it("shows an error when the search fails", async () => {
    api.searchFoods.mockRejectedValue(new Error("down"))
    renderWithQuery(<FoodPage />)
    expect(await screen.findByText("Search isn’t available")).toBeInTheDocument()
  })

  it("logs a quick add, calculating calories from the macros", async () => {
    api.addEntry.mockImplementation((input) => Promise.resolve({ ...input, id: "e-new" }))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.click(within(dialog).getByRole("radio", { name: "Snacks" }))
    await user.type(within(dialog).getByLabelText("Name"), "Protein bar")
    await user.type(within(dialog).getByLabelText("Protein"), "20")
    await user.type(within(dialog).getByLabelText("Carbs"), "25")
    await user.type(within(dialog).getByLabelText("Fat"), "8")
    expect(within(dialog).getByText("Calories will be calculated: 252 kcal")).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Add to Snacks" }))

    await waitFor(() =>
      expect(api.addEntry).toHaveBeenCalledWith({
        date: today,
        meal: "snacks",
        name: "Protein bar",
        amountLabel: "Quick add",
        source: "quick-add",
        calories: 252,
        protein: 20,
        carbs: 25,
        fat: 8,
      }),
    )
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("asks before keeping quick-add calories that don't match the macros", async () => {
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.type(within(dialog).getByRole("textbox", { name: "Calories" }), "300")
    await user.type(within(dialog).getByRole("textbox", { name: "Protein" }), "10")
    expect(within(dialog).getByText("Calories don’t match macros")).toBeInTheDocument()

    await user.click(within(dialog).getByRole("button", { name: "Use 40 kcal" }))
    expect(within(dialog).getByRole("textbox", { name: "Calories" })).toHaveValue("40")
    expect(within(dialog).getByText("Calories match macros (40 kcal)")).toBeInTheDocument()
  })

  it("refuses a quick add with nothing entered", async () => {
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.click(within(dialog).getByRole("button", { name: /Add to/ }))

    expect(await within(dialog).findByText("Enter calories or at least one macro")).toBeInTheDocument()
    expect(api.addEntry).not.toHaveBeenCalled()
  })

  it("carries a quick add over to a custom food, saves it and logs one serving", async () => {
    api.createCustomFood.mockImplementation((food) => Promise.resolve({ ...food, id: "f-bar", source: "custom" }))
    api.addEntry.mockImplementation((input) => Promise.resolve({ ...input, id: "e-new" }))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    let dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.type(within(dialog).getByLabelText("Name"), "Protein bar")
    await user.type(within(dialog).getByRole("textbox", { name: "Protein" }), "20")
    await user.type(within(dialog).getByRole("textbox", { name: "Carbs" }), "25")
    await user.type(within(dialog).getByRole("textbox", { name: "Fat" }), "8")
    await user.click(within(dialog).getByRole("button", { name: "Save as custom food instead" }))

    dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    expect(within(dialog).getByLabelText("Food name")).toHaveValue("Protein bar")
    expect(within(dialog).getByRole("textbox", { name: "Calories" })).toHaveValue("252")
    await user.click(within(dialog).getByRole("button", { name: /Save & log to/ }))

    await waitFor(() =>
      expect(api.createCustomFood).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Protein bar", servingSize: 1, servingUnit: "piece", nutrition: { calories: 252, protein: 20, carbs: 25, fat: 8 } }),
      ),
    )
    await waitFor(() => expect(api.addEntry).toHaveBeenCalledWith(expect.objectContaining({ foodId: "f-bar", quantity: 1, quantityUnit: "serving" })))
  })

  it("saves a custom food without logging it", async () => {
    api.createCustomFood.mockImplementation((food) => Promise.resolve({ ...food, id: "f-rice", source: "custom" }))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.click(within(dialog).getByRole("tab", { name: "Custom food" }))
    await user.type(within(dialog).getByLabelText("Food name"), "Mum's fried rice")
    await user.type(within(dialog).getByRole("textbox", { name: "Calories" }), "500")
    await user.type(within(dialog).getByRole("textbox", { name: "Protein" }), "15")
    await user.type(within(dialog).getByRole("textbox", { name: "Carbs" }), "70")
    await user.type(within(dialog).getByRole("textbox", { name: "Fat" }), "18")
    await user.click(within(dialog).getByRole("button", { name: /More nutrients/ }))
    await user.type(within(dialog).getByLabelText("Fibre"), "3")
    await user.click(within(dialog).getByRole("button", { name: "Save only" }))

    await waitFor(() => expect(api.createCustomFood).toHaveBeenCalledWith(expect.objectContaining({ name: "Mum's fried rice", fibreG: 3 })))
    expect(toast.success).toHaveBeenCalledWith("Saved Mum's fried rice", { description: "Find it in search under My food." })
    expect(api.addEntry).not.toHaveBeenCalled()
  })

  it("keeps the custom food form open when saving fails", async () => {
    api.createCustomFood.mockRejectedValue(new Error("down"))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.click(within(dialog).getByRole("tab", { name: "Custom food" }))
    await user.click(within(dialog).getByRole("button", { name: "Save only" }))
    expect(await within(dialog).findByText("Give the food a name")).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText("Food name"), "Kaya toast")
    await user.type(within(dialog).getByRole("textbox", { name: "Calories" }), "300")
    await user.type(within(dialog).getByRole("textbox", { name: "Protein" }), "6")
    await user.type(within(dialog).getByRole("textbox", { name: "Carbs" }), "40")
    await user.type(within(dialog).getByRole("textbox", { name: "Fat" }), "12")
    await user.click(within(dialog).getByRole("button", { name: "Save only" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Couldn’t save that food", expect.anything()))
    expect(screen.getByRole("dialog", { name: "Add food manually" })).toBeInTheDocument()
  })

  it("edits a quick add's values, sending only what changed", async () => {
    api.updateEntry.mockResolvedValue({ ...rice, calories: 650 })
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)

    await user.click(await screen.findByRole("button", { name: "Edit Chicken rice" }))
    const dialog = await screen.findByRole("dialog", { name: "Edit food" })
    await user.clear(within(dialog).getByRole("textbox", { name: "Calories" }))
    await user.type(within(dialog).getByRole("textbox", { name: "Calories" }), "650")
    await user.click(within(dialog).getByRole("radio", { name: "Dinner" }))
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledWith("e-rice", { meal: "dinner", calories: 650 }))
    expect(toast.success).toHaveBeenCalledWith("Updated Chicken rice", { description: "650 kcal" })
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("edits a saved food's entry by its amount", async () => {
    const logged: FoodEntry = { ...rice, id: "e-chicken", name: "Chicken breast", amountLabel: "100 g", source: "database", calories: 165, protein: 31, carbs: 0, fat: 3.6, foodId: "f-chicken", quantity: 100, quantityUnit: "g" }
    api.getFoodLog.mockResolvedValue({ date: today, entries: [logged] })
    api.getFood.mockResolvedValue(chicken)
    api.updateEntry.mockResolvedValue({ ...logged, calories: 248 })
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)

    await user.click(await screen.findByRole("button", { name: "Edit Chicken breast" }))
    const dialog = await screen.findByRole("dialog", { name: "Edit food" })
    const amount = await within(dialog).findByLabelText("Amount")
    expect(within(dialog).getByRole("button", { name: "Save changes" })).toBeDisabled()
    await user.clear(amount)
    await user.type(amount, "150")
    expect(within(dialog).getByText("248")).toBeInTheDocument()
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }))

    await waitFor(() => expect(api.updateEntry).toHaveBeenCalledWith("e-chicken", { quantity: 150 }))
  })

  it("removes an entry at once and puts it back if the server refuses", async () => {
    let refuse!: (error: Error) => void
    api.removeEntry.mockReturnValue(new Promise((_, reject) => (refuse = reject)))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)

    await user.click(await screen.findByRole("button", { name: "Remove Chicken rice" }))
    await waitFor(() => expect(screen.queryByText("Chicken rice")).not.toBeInTheDocument())

    refuse(new Error("down"))
    expect(await screen.findByText("Chicken rice")).toBeInTheDocument()
    expect(toast.error).toHaveBeenCalledWith("Couldn’t remove that item", expect.anything())
  })

  it("offers a retry when the log can't be loaded", async () => {
    api.getFoodLog.mockRejectedValueOnce(new Error("down"))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)

    expect(await screen.findByText("Couldn’t load your food log")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Retry" }))
    expect(await screen.findByText("Chicken rice")).toBeInTheDocument()
  })

  it("says scanning isn't available yet", async () => {
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Barcode" }))
    expect(toast).toHaveBeenCalledWith("Barcode scanning is coming soon", expect.anything())
  })
})
