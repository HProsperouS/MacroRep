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
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible()
  return email
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
  return headers
}
