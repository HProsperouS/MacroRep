import { expect, PASSWORD, signUpInBrowser, test } from "./fixtures"

test("signs up, stays signed in across a reload, signs out and back in", async ({ page }) => {
  const email = await signUpInBrowser(page)

  // The access token lives in memory only; the refresh cookie restores the session.
  await page.reload()
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible()

  await page.getByRole("button", { name: "Sign out" }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto("/food")
  await expect(page).toHaveURL(/\/login$/)

  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(PASSWORD)
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible()
})

test("refuses a wrong password", async ({ page }) => {
  const email = await signUpInBrowser(page)
  await page.getByRole("button", { name: "Sign out" }).click()

  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill("not-the-password")
  await page.getByRole("button", { name: "Sign in" }).click()

  await expect(page.getByText("Couldn’t sign you in")).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})
