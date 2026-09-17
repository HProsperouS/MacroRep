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
  config.headers.set("X-Correlation-ID", crypto.randomUUID())
  return config
})

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
