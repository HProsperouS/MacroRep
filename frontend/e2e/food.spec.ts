import { expect, isoDate, signUpInBrowser, test } from "./fixtures"

test("logs a food from search and keeps it after a reload", async ({ page }) => {
  await signUpInBrowser(page)
  await page.getByRole("navigation").getByRole("link", { name: "Food" }).click()
  await expect(page.getByText("0 / 2,200 kcal")).toBeVisible()

  await page.getByRole("radio", { name: "Lunch" }).click()
  await page.getByRole("searchbox", { name: "Search foods" }).fill("chicken")
  await page.getByRole("button", { name: /Chicken breast, grilled/ }).click()
  const amount = page.getByRole("region", { name: "Amount of Chicken breast, grilled" })
  await amount.getByRole("textbox", { name: "Amount" }).fill("200")
  await amount.getByRole("button", { name: "Add to Lunch" }).click()

  await expect(page.getByText("Added Chicken breast, grilled to Lunch")).toBeVisible()
  await expect(page.getByText("330 / 2,200 kcal")).toBeVisible()

  await page.reload()
  await expect(page.getByText("330 / 2,200 kcal")).toBeVisible()
  await expect(page.getByRole("button", { name: "Edit Chicken breast, grilled" })).toBeVisible()

  // Another day from the calendar: the browser's own picker opens (a real click allows it),
  // and the day chosen in it is shown.
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.getByRole("button", { name: "Choose a day" }).click()
  await page.keyboard.press("Escape")
  await page.getByLabel("Day", { exact: true }).fill(isoDate(1))
  await expect(page.getByRole("heading", { level: 1, name: "Yesterday" })).toBeVisible()
  await expect(page.getByText("0 / 2,200 kcal")).toBeVisible()
  expect(errors, "opening the picker throws nothing").toEqual([])
})
