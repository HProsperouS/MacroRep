import { expect, test as base, type APIRequestContext, type Page, type Request } from "@playwright/test"

export { expect }

export const PASSWORD = "long-enough-pw"

/** Fails the test on any 5xx from the API: the UI may recover from one, but the server shouldn't throw. */
export const test = base.extend<{ serverErrors: void }>({
  serverErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      const inFlight = new Set<Request>()
      const isApi = (request: Request) => new URL(request.url()).pathname.startsWith("/api/")
      page.on("request", (request) => {
        // Loading a new document cancels the old one's requests, and those report no end.
        if (request.isNavigationRequest() && request.frame() === page.mainFrame()) inFlight.clear()
        else if (isApi(request)) inFlight.add(request)
      })
      page.on("requestfinished", (request) => inFlight.delete(request))
      page.on("requestfailed", (request) => inFlight.delete(request))
      page.on("response", (response) => {
        if (response.status() >= 500) errors.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      })
      await use()
      // A test can pass while the page is still loading; wait for those answers too.
      await expect
        .poll(() => [...inFlight].map((request) => `${request.method()} ${request.url()}`), {
          message: "requests still in flight",
        })
        .toEqual([])
      expect(errors, "server errors").toEqual([])
    },
    { auto: true },
  ],
})

export function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
}

/**
 * Waits out the last minute of the UTC day, so data dated by the test and the server's own
 * "today" (taken later, e.g. when a check-in starts) fall on the same day.
 */
export async function awayFromMidnight() {
  const msToMidnight = 86_400_000 - (Date.now() % 86_400_000)
  if (msToMidnight >= 60_000) return
  test.info().setTimeout(test.info().timeout + msToMidnight + 1_000)
  await new Promise((resolve) => setTimeout(resolve, msToMidnight + 1_000))
}

/** A date `daysAgo` days before today, in the browser's zone (UTC, see playwright.config.ts). */
export function isoDate(daysAgo = 0) {
  return new Date(Date.now() - daysAgo * 86_400_000).toISOString().slice(0, 10)
}

export async function signUpInBrowser(page: Page, email = uniqueEmail()) {
  await page.goto("/register")
  await page.getByLabel("Name").fill("E2E User")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(PASSWORD)
  await page.getByRole("button", { name: "Create account" }).click()
  await finishGuideInBrowser(page)
  return email
}

/**
 * Goes through the sign-up guide a new account is sent to. Its targets are estimated from the
 * details; the tests then set 2,200 kcal, so their expected totals don't depend on the formula.
 */
async function finishGuideInBrowser(page: Page) {
  const next = page.getByRole("button", { name: "Continue" })
  await expect(page.getByRole("heading", { name: "About you" })).toBeVisible()
  await page.getByLabel("Date of birth").fill("1995-04-20")
  await page.getByRole("radio", { name: "Male", exact: true }).click()
  await page.getByLabel("Height").fill("175")
  await page.getByLabel("Weight today").fill("80")
  await next.click()
  await page.getByRole("radio", { name: "Maintain" }).click()
  await next.click()
  await page.getByRole("radio", { name: "Beginner" }).click()
  await page.getByLabel("Training days").fill("3")
  await page.getByRole("combobox", { name: "Activity level" }).click()
  await page.getByRole("option", { name: "Moderately active, exercise 3–5 days a week" }).click()
  await next.click()
  await page.getByRole("button", { name: "Barbell" }).click()
  await next.click()
  await expect(page.getByText(/^Estimated for you:/)).toBeVisible()
  for (const [label, value] of [
    ["Calories", "2200"],
    ["Protein", "150"],
    ["Carbs", "230"],
    ["Fat", "70"],
  ]) {
    await page.getByLabel(label, { exact: true }).fill(value)
  }
  await page.getByRole("button", { name: "Finish setup" }).click()
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible()
}

/**
 * Signs up through the API with the page's own request context, so the refresh cookie lands
 * in the browser and the next page load is signed in. Returns headers for further API calls.
 */
export async function signUpThroughApi(request: APIRequestContext) {
  const response = await request.post("/api/v1/auth/register", {
    data: { name: "E2E User", email: uniqueEmail(), password: PASSWORD },
  })
  expect(response.status()).toBe(201)
  const { accessToken } = (await response.json()) as { accessToken: string }
  const headers = { Authorization: `Bearer ${accessToken}` }
  const timezone = await request.put("/api/v1/profile/timezone", { headers, data: { timezone: "UTC" } })
  expect(timezone.status()).toBe(200)
  // Past the sign-up guide, keeping the starting targets and a maintain goal.
  const targets = await (await request.get("/api/v1/nutrition/targets", { headers })).json()
  const guide = await request.post("/api/v1/profile/onboarding", {
    headers,
    data: {
      name: "E2E User",
      heightCm: 175,
      goal: "maintain",
      weeklyRateKg: 0,
      trainingDaysPerWeek: 3,
      experienceLevel: "beginner",
      equipment: ["barbell"],
      dateOfBirth: "1995-04-20",
      sex: "male",
      activityLevel: "moderate",
      weightKg: 80,
      targets,
    },
  })
  expect(guide.status()).toBe(200)
  return headers
}
