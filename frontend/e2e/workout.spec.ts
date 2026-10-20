import { expect, signUpInBrowser, test } from "./fixtures"

test("logs a workout and finds it in history", async ({ page }) => {
  await signUpInBrowser(page)
  await page.getByRole("navigation").getByRole("link", { name: "Workout" }).click()
  await page.getByRole("button", { name: "Start empty workout" }).click()

  await page.getByRole("button", { name: "Add exercises" }).click()
  const picker = page.getByRole("dialog", { name: "Add exercises" })
  await picker.getByRole("button", { name: /Barbell Bench Press/ }).click()
  await picker.getByRole("button", { name: "Add 1 exercise" }).click()

  for (const set of [1, 2, 3]) {
    await page.getByRole("textbox", { name: `Barbell Bench Press set ${set} weight in kg` }).fill("60")
    await page.getByRole("textbox", { name: `Barbell Bench Press set ${set} reps` }).fill("8")
    await page.getByRole("button", { name: `Complete Barbell Bench Press set ${set}` }).click()
  }

  await page.getByRole("button", { name: "Finish workout" }).click()

  await expect(page.getByRole("heading", { level: 1, name: "Nice work" })).toBeVisible()
  await expect(page.getByRole("main")).toContainText("Volume1,440kg")

  await page.goto("/workout/history")
  const history = page.getByRole("main").getByRole("listitem")
  await expect(history).toHaveCount(1)
  await expect(history).toContainText("Freestyle workout")
  await expect(history).toContainText("1 exercise · 3 sets · 1,440 kg")
})
