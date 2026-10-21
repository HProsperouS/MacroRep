import path from "node:path"

import { expect, signUpInBrowser, test } from "./fixtures"

// A real photo, so the browser really decodes and scales it. The end-to-end backend runs the
// rule-based model, which "sees" the same plate in every photo.
const PHOTO = path.join(import.meta.dirname, "../../backend/evals/photos/banana.jpg")

test("estimates a meal photo, then logs only what the user confirms", async ({ page }) => {
  await signUpInBrowser(page)
  await page.getByRole("navigation").getByRole("link", { name: "Food" }).click()
  await expect(page.getByText("0 / 2,200 kcal")).toBeVisible()

  const sent = page.waitForRequest((request) => request.url().endsWith("/food/photo-estimates"))
  await page.getByLabel("Meal photo").setInputFiles(PHOTO)
  const image = (await sent).postDataJSON().image as string

  expect(image.startsWith("data:image/jpeg;base64,")).toBe(true)
  // Measured in the page, where images can be decoded (the e2e code has no DOM types).
  const size = await page.evaluate<number>(
    `(async (url) => { const img = document.createElement("img"); img.src = url; await img.decode(); return Math.max(img.width, img.height) })(${JSON.stringify(image)})`,
  )
  expect(size).toBeGreaterThan(0)
  expect(size).toBeLessThanOrEqual(1024)

  const dialog = page.getByRole("dialog", { name: "Check the photo estimate" })
  await expect(dialog.getByRole("listitem", { name: "Chicken rice" })).toBeVisible()
  await expect(page.getByText("0 / 2,200 kcal")).toBeVisible() // nothing logged yet
  await dialog.getByRole("button", { name: "Remove Cucumber slices" }).click()
  await dialog.getByRole("radio", { name: "Lunch" }).click()
  await dialog.getByRole("button", { name: "Log 1 item to Lunch" }).click()

  await expect(page.getByText("600 / 2,200 kcal")).toBeVisible()
  await page.reload()
  await expect(page.getByText("600 / 2,200 kcal")).toBeVisible()
  await expect(page.getByText("350 g · photo estimate")).toBeVisible()
})
