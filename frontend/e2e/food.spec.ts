import { expect, signUpInBrowser, test } from "./fixtures"

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
})
