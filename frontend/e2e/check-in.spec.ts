import { awayFromMidnight, expect, isoDate, signUpThroughApi, test } from "./fixtures"

test("runs a check-in and applies its calorie proposal", async ({ page }) => {
  await awayFromMidnight()
  // A week the coach acts on: every day logged at 2,000 kcal on a maintain goal, and the
  // weight down 2 kg, so it proposes raising the 2,200 kcal target (by at most 300).
  const headers = await signUpThroughApi(page.request)
  for (let daysAgo = 0; daysAgo < 7; daysAgo++) {
    const entry = await page.request.post("/api/v1/food-log/entries", {
      headers,
      data: {
        date: isoDate(daysAgo),
        meal: "lunch",
        name: "Test meal",
        amountLabel: "1 plate",
        source: "quick-add",
        calories: 2000,
        protein: 100,
        carbs: 200,
        fat: 60,
      },
    })
    expect(entry.status()).toBe(201)
  }
  for (const [daysAgo, weightKg] of [
    [6, 80],
    [0, 78],
  ]) {
    const weighIn = await page.request.post("/api/v1/body/weigh-ins", {
      headers,
      data: { date: isoDate(daysAgo), weightKg },
    })
    expect(weighIn.status()).toBe(201)
  }

  await page.goto("/coach")
  await page.getByRole("button", { name: "Start check-in" }).click()

  // Generated in the background; the page polls until it's ready.
  await expect(page.getByText("Needs review")).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole("row", { name: "Daily calories 2,200 2,500 +300" })).toBeVisible()

  await page.getByRole("button", { name: "Apply", exact: true }).click()
  await expect(page.getByRole("button", { name: "Apply", exact: true })).toBeHidden()

  await page.getByRole("navigation").getByRole("link", { name: "Food" }).click()
  await expect(page.getByText("2,000 / 2,500 kcal")).toBeVisible()
})
