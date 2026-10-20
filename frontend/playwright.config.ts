import { defineConfig, devices } from "@playwright/test"

// End-to-end tests: the production build (`vite preview`, proxying /api like CloudFront would)
// in front of the real backend on PostgreSQL. The database must exist; it's migrated on
// start. Tests sign up their own users, so they don't need it empty.
const BACKEND_PORT = 8001
const FRONTEND_PORT = 4173
const DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://macrorep:local-development-only@localhost:5432/macrorep_e2e"

const backend = "uv run --project ../backend --locked"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  // No retries: a 5xx that shows up only sometimes is exactly what these tests should report.
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    // The user's "today" follows the browser's zone; the tests compute dates in the same one.
    timezoneId: "UTC",
    // The PWA's service worker would serve cached pages between tests.
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [{ name: "desktop", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        `${backend} alembic -c ../backend/alembic.ini upgrade head && ` +
        `${backend} uvicorn app.main:app --app-dir ../backend --port ${BACKEND_PORT}`,
      url: `http://127.0.0.1:${BACKEND_PORT}/health/ready`,
      // Never a server already running: it could be an old build or use another database.
      reuseExistingServer: false,
      timeout: 120_000,
      // Everything that changes behaviour is set here, since the backend also reads a
      // developer's backend/.env and these take precedence over it.
      env: {
        APP_ENV: "test",
        DATABASE_URL,
        API_PREFIX: "/api/v1",
        AUTO_CREATE_SCHEMA: "false",
        // The shared food and exercise catalog. Tests sign up their own users.
        SEED_DEMO_DATA: "true",
        PREVIEW_AUTH_ENABLED: "false",
        REFRESH_COOKIE_PATH: "/api/v1/auth",
        REFRESH_COOKIE_SAMESITE: "strict",
        REFRESH_COOKIE_SECURE: "false",
        COACH_MODEL_PROVIDER: "fake",
        DEBUG: "false",
        LOG_JSON: "false",
        LOG_DIR: "",
      },
    },
    {
      command: `npm run build && npx vite preview --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_API_BASE_URL: "/api/v1",
        VITE_DEV_PROXY_TARGET: `http://127.0.0.1:${BACKEND_PORT}`,
      },
    },
  ],
})
