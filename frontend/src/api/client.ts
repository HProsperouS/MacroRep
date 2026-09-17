import axios, { AxiosError } from "axios"

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

export const apiClient = axios.create({
  baseURL: configuredBaseUrl || "/api",
  timeout: 15_000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
})

// TODO: attach the JWT from the auth flow once lib/auth is implemented.
apiClient.interceptors.request.use((config) => {
  config.headers.set("X-Correlation-ID", createRequestId())
  return config
})

/**
 * Mock API: until the FastAPI backend is ready, requests are answered in-memory.
 * Defaults to on in `npm run dev`; set VITE_USE_MOCK_API=false to hit the real backend.
 * The dynamic import keeps the mock (and its sample data) out of production bundles.
 */
const mockSetting = import.meta.env.VITE_USE_MOCK_API
const useMockApi = mockSetting ? mockSetting === "true" : import.meta.env.DEV

if (useMockApi) {
  apiClient.defaults.adapter = async (config) => {
    const { mockAdapter } = await import("@/api/mock/mock-adapter")
    return mockAdapter(config)
  }
}

export function apiErrorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const payload = error.response?.data as { detail?: unknown; message?: unknown } | undefined
    if (typeof payload?.message === "string") return payload.message
    if (typeof payload?.detail === "string") return payload.detail
    if (error.code === "ECONNABORTED") return "The request timed out. Please try again."
    if (!error.response) return "MacroRep could not reach the server. Check your connection and try again."
  }
  return "Something went wrong. Please try again."
}

/** crypto.randomUUID is only available on secure origins (https/localhost). */
export function createRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}
