import { fireEvent, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { AxiosError } from "axios"
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
  suggestFoods: vi.fn(),
  getFood: vi.fn(),
  createCustomFood: vi.fn(),
  getTargets: vi.fn(),
  estimatePhoto: vi.fn(),
}))
vi.mock("@/api/food-api", () => ({ foodApi: api }))
// jsdom can't decode or draw images; the resizing is the browser's job.
vi.mock("@/lib/photo", () => ({ photoToDataUrl: vi.fn().mockResolvedValue("data:image/jpeg;base64,AA==") }))
vi.mock("@/hooks/use-media-query")

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
  api.suggestFoods.mockResolvedValue({ recent: [], common: [chicken] })
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

  it("jumps to a day chosen from the calendar", async () => {
    const showPicker = vi.fn()
    HTMLInputElement.prototype.showPicker = showPicker
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Choose a day" }))
    expect(showPicker).toHaveBeenCalledOnce()
    const day = screen.getByLabelText("Day")
    expect(day).toHaveAttribute("max", "2026-10-20")
    fireEvent.change(day, { target: { value: "2026-10-15" } })

    expect(await screen.findByText("Thursday, 15 October")).toBeInTheDocument()
    await waitFor(() => expect(api.getFoodLog).toHaveBeenLastCalledWith("2026-10-15", expect.anything()))
    delete (HTMLInputElement.prototype as Partial<HTMLInputElement>).showPicker // jsdom has none
  })

  it("ignores a future day typed into the calendar", async () => {
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    fireEvent.change(screen.getByLabelText("Day"), { target: { value: "2026-10-25" } })

    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument()
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

  it("shows an error when the suggestions can't be loaded", async () => {
    api.suggestFoods.mockRejectedValue(new Error("down"))
    renderWithQuery(<FoodPage />)
    expect(await screen.findByText("Couldn’t load suggestions")).toBeInTheDocument()
  })

  it("shows an error when the search fails", async () => {
    api.searchFoods.mockRejectedValue(new Error("down"))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.type(screen.getByRole("searchbox", { name: "Search foods" }), "laksa")
    expect(await screen.findByText("Search isn’t available")).toBeInTheDocument()
  })

  it("offers what the user ate lately first, then more foods, before anything is searched", async () => {
    const egg = { ...chicken, id: "f-egg", name: "Egg, whole" }
    api.suggestFoods.mockResolvedValue({ recent: [egg], common: [chicken] })
    renderWithQuery(<FoodPage />)

    const recent = await screen.findByRole("region", { name: "Recently eaten" })
    expect(within(recent).getByText("Egg, whole")).toBeInTheDocument()
    expect(within(screen.getByRole("region", { name: "More foods" })).getByText("Chicken breast")).toBeInTheDocument()
    expect(api.searchFoods).not.toHaveBeenCalled()
  })

  it("says so when there's nothing to suggest yet", async () => {
    api.suggestFoods.mockResolvedValue({ recent: [], common: [] })
    renderWithQuery(<FoodPage />)
    expect(await screen.findByText("No foods to suggest yet")).toBeInTheDocument()
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

  it("asks a custom food for only what the app uses, and logs it once saved", async () => {
    api.createCustomFood.mockImplementation((food) => Promise.resolve({ ...food, id: "f-rice", source: "custom" }))
    api.addEntry.mockImplementation((input) => Promise.resolve({ ...input, id: "e-new" }))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.click(within(dialog).getByRole("tab", { name: "Custom food" }))
    expect(within(dialog).queryByLabelText(/Brand/)).not.toBeInTheDocument()
    expect(within(dialog).queryByRole("button", { name: /More nutrients/ })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole("button", { name: "Save only" })).not.toBeInTheDocument()
    await user.type(within(dialog).getByLabelText("Food name"), "Mum's fried rice")
    await user.type(within(dialog).getByRole("textbox", { name: "Calories" }), "500")
    await user.type(within(dialog).getByRole("textbox", { name: "Protein" }), "15")
    await user.type(within(dialog).getByRole("textbox", { name: "Carbs" }), "70")
    await user.type(within(dialog).getByRole("textbox", { name: "Fat" }), "18")
    await user.click(within(dialog).getByRole("button", { name: /Save & log to/ }))

    await waitFor(() =>
      expect(api.createCustomFood).toHaveBeenCalledWith({
        name: "Mum's fried rice",
        servingSize: 1,
        servingUnit: "piece",
        servingWeightG: undefined,
        nutrition: { calories: 500, protein: 15, carbs: 70, fat: 18 },
      }),
    )
    await waitFor(() => expect(api.addEntry).toHaveBeenCalledWith(expect.objectContaining({ foodId: "f-rice", quantity: 1 })))
  })

  it("keeps the custom food form open when saving fails", async () => {
    api.createCustomFood.mockRejectedValue(new Error("down"))
    const user = userEvent.setup()
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    await user.click(screen.getByRole("button", { name: "Quick add" }))
    const dialog = await screen.findByRole("dialog", { name: "Add food manually" })
    await user.click(within(dialog).getByRole("tab", { name: "Custom food" }))
    await user.click(within(dialog).getByRole("button", { name: /Save & log to/ }))
    expect(await within(dialog).findByText("Give the food a name")).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText("Food name"), "Kaya toast")
    await user.type(within(dialog).getByRole("textbox", { name: "Calories" }), "300")
    await user.type(within(dialog).getByRole("textbox", { name: "Protein" }), "6")
    await user.type(within(dialog).getByRole("textbox", { name: "Carbs" }), "40")
    await user.type(within(dialog).getByRole("textbox", { name: "Fat" }), "12")
    await user.click(within(dialog).getByRole("button", { name: /Save & log to/ }))

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

  it("offers no barcode scanning, which isn't built", async () => {
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")

    expect(screen.queryByRole("button", { name: /barcode/i })).not.toBeInTheDocument()
  })
})

describe("Meal photos", () => {
  const plate = {
    items: [
      { name: "Chicken rice", portion: "1 plate", grams: 350, calories: 600, protein: 30, carbs: 75, fat: 18 },
      { name: "Iced tea", portion: "1 glass", grams: 300, calories: 90, protein: 0, carbs: 22, fat: 0 },
    ],
    note: "Hidden oil in the rice is hard to judge.",
  }
  const photoFile = () => new File([new Uint8Array([0xff, 0xd8, 0xff])], "meal.jpg", { type: "image/jpeg" })

  async function scan(user: ReturnType<typeof userEvent.setup>) {
    renderWithQuery(<FoodPage />)
    await screen.findByText("Chicken rice")
    await user.upload(screen.getByLabelText("Meal photo"), photoFile())
    return screen.findByRole("dialog", { name: "Check the photo estimate" })
  }

  it("shows the estimate, scales an item by its amount, and logs what's kept", async () => {
    api.estimatePhoto.mockResolvedValue(plate)
    api.addEntry.mockImplementation((input) => Promise.resolve({ ...input, id: `e-${input.name}` }))
    const user = userEvent.setup()
    const dialog = await scan(user)

    expect(await within(dialog).findByText("Hidden oil in the rice is hard to judge.")).toBeInTheDocument()
    expect(api.estimatePhoto).toHaveBeenCalledWith("data:image/jpeg;base64,AA==")
    const rice = within(dialog).getByRole("listitem", { name: "Chicken rice" })
    await user.clear(within(rice).getByLabelText("Amount"))
    await user.type(within(rice).getByLabelText("Amount"), "175")
    expect(within(rice).getByLabelText("Calories")).toHaveValue("300")
    expect(within(rice).getByLabelText("Protein")).toHaveValue("15")
    await user.click(within(dialog).getByRole("button", { name: "Remove Iced tea" }))
    await user.click(within(dialog).getByRole("radio", { name: "Dinner" }))
    await user.click(within(dialog).getByRole("button", { name: "Log 1 item to Dinner" }))

    await waitFor(() =>
      expect(api.addEntry).toHaveBeenCalledWith({
        date: today,
        meal: "dinner",
        name: "Chicken rice",
        amountLabel: "175 g · photo estimate",
        source: "photo",
        calories: 300,
        protein: 15,
        carbs: 37.5,
        fat: 9,
      }),
    )
    expect(api.addEntry).toHaveBeenCalledOnce()
    expect(toast.success).toHaveBeenCalledWith("Added 1 item to Dinner", { description: "300 kcal" })
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument())
  })

  it("won't log calories far below the macros, or an unnamed item", async () => {
    api.estimatePhoto.mockResolvedValue(plate)
    const user = userEvent.setup()
    const dialog = await scan(user)

    const rice = await within(dialog).findByRole("listitem", { name: "Chicken rice" })
    await user.clear(within(rice).getByLabelText("Calories"))
    await user.type(within(rice).getByLabelText("Calories"), "60")
    expect(within(rice).getByText(/Too low for these macros/)).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Log 2 items to Lunch" })).toBeDisabled()

    await user.clear(within(rice).getByLabelText("Calories"))
    await user.type(within(rice).getByLabelText("Calories"), "600")
    await user.click(within(dialog).getByRole("button", { name: "Add an item" }))
    expect(within(dialog).getByText("Enter a name")).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Log 3 items to Lunch" })).toBeDisabled()
    expect(api.addEntry).not.toHaveBeenCalled()
  })

  it("keeps what didn't save when logging stops part way", async () => {
    api.estimatePhoto.mockResolvedValue(plate)
    api.addEntry.mockResolvedValueOnce({ id: "e1" }).mockRejectedValueOnce(new Error("down"))
    const user = userEvent.setup()
    const dialog = await scan(user)

    await user.click(await within(dialog).findByRole("button", { name: "Log 2 items to Lunch" }))

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Logged 1 of 2; the rest didn’t save", expect.anything()))
    expect(within(dialog).queryByRole("listitem", { name: "Chicken rice" })).not.toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Log 1 item to Lunch" })).toBeInTheDocument()
  })

  it("labels the entry with the amount as entered", async () => {
    api.estimatePhoto.mockResolvedValue({ items: [plate.items[0]], note: null })
    api.addEntry.mockImplementation((input) => Promise.resolve({ ...input, id: "e1" }))
    const user = userEvent.setup()
    const dialog = await scan(user)

    const rice = await within(dialog).findByRole("listitem", { name: "Chicken rice" })
    await user.clear(within(rice).getByLabelText("Amount"))
    await user.type(within(rice).getByLabelText("Amount"), "12.5")
    await user.click(within(dialog).getByRole("button", { name: "Log 1 item to Lunch" }))

    await waitFor(() => expect(api.addEntry).toHaveBeenCalledWith(expect.objectContaining({ amountLabel: "12.5 g · photo estimate" })))
  })

  it("says when no food was found", async () => {
    api.estimatePhoto.mockResolvedValue({ items: [], note: "This looks like a keyboard." })
    const user = userEvent.setup()
    const dialog = await scan(user)

    expect(await within(dialog).findByText("No food was found in this photo.")).toBeInTheDocument()
    expect(within(dialog).getByRole("button", { name: "Log 0 items to Lunch" })).toBeDisabled()
  })

  it("explains a photo that couldn't be read", async () => {
    api.estimatePhoto.mockRejectedValue(
      new AxiosError("429", "ERR_BAD_REQUEST", undefined, undefined, {
        status: 429,
        data: { detail: "That's a lot of photos for now. Try again in 20 minutes." },
      } as never),
    )
    const user = userEvent.setup()
    const dialog = await scan(user)

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Try again in 20 minutes.")
    expect(within(dialog).getByRole("button", { name: "Choose another photo" })).toBeInTheDocument()
  })
})
