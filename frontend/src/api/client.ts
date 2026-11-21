import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios"

import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/auth"
import type { AccessToken } from "@/types/auth"

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

export const apiClient = axios.create({
  baseURL: configuredBaseUrl || "/api/v1",
  timeout: 15_000,
  // Same-origin requests (the dev proxy, and a single-origin deployment) carry
  // cookies regardless; this is what makes it work if the API ever moves.
  withCredentials: true,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
})

/**
 * Only the credential-issuing endpoints (and asking for a reset code, which needs no
 * session either) must skip the refresh-and-retry below:
 * a wrong password on `/auth/login` must reach the form as a 401, not get
 * treated as an expired-token retry. `/auth/logout`, unlike those two, does
 * require a session — it must NOT be excluded, or logging out with an
 * already-expired access token silently fails to revoke the refresh token
 * server-side while the UI still shows the user as signed out.
 */
const CREDENTIAL_ROUTES = new Set(["/auth/register", "/auth/login", "/auth/password-reset", "/auth/password-reset/confirm"])
const isCredentialRoute = (url?: string) => url !== undefined && CREDENTIAL_ROUTES.has(url)

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

/**
 * The refresh token is an httpOnly cookie, so nothing is passed explicitly here
 * — `withCredentials` is what puts it on the wire. Going through a bare axios
 * call keeps this off apiClient's interceptors, which would otherwise recurse.
 */
async function refreshAccessToken() {
  const { data } = await axios.post<AccessToken>(
    `${apiClient.defaults.baseURL}/auth/refresh`,
    null,
    { withCredentials: true, headers: { Accept: "application/json" } },
  )
  setAccessToken(data.accessToken)
  return data.accessToken
}

/** Held in a module variable so a burst of 401s triggers one refresh, not one each. */
let refreshInFlight: Promise<string> | null = null

function refreshOnce() {
  refreshInFlight ??= refreshAccessToken().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

/**
 * Boot probe: does this browser still hold a usable refresh cookie? Because the
 * cookie is httpOnly, the client cannot tell by looking — it has to ask. Reports
 * the answer instead of redirecting, so the caller decides what it means.
 */
export async function restoreSession() {
  if (getAccessToken()) return true
  try {
    await refreshOnce()
    return true
  } catch {
    clearAccessToken()
    return false
  }
}

/** The server's answer when a device's session was ended elsewhere (app/identity/dependencies.py). */
const SESSION_ENDED = "Session ended"
/** Why the last session ended, kept across the redirect for the sign-in page to show once. */
const SIGNED_OUT_KEY = "macrorep.signed-out"

export type SignedOutReason = "elsewhere"

function endSession(reason?: SignedOutReason) {
  clearAccessToken()
  if (reason) {
    try {
      window.sessionStorage.setItem(SIGNED_OUT_KEY, reason)
    } catch {
      // Storage blocked: the sign-in page just won't say why.
    }
  }
  if (window.location.pathname !== "/login") window.location.assign("/login")
}

/** Why this browser was last signed out, if the app knows: its session was ended by a sign-in on
 * another device, or a password change. Read it, then `forgetSignedOutReason` once shown. */
export function signedOutReason(): SignedOutReason | null {
  try {
    return window.sessionStorage.getItem(SIGNED_OUT_KEY) === "elsewhere" ? "elsewhere" : null
  } catch {
    return null
  }
}

export function forgetSignedOutReason() {
  try {
    window.sessionStorage.removeItem(SIGNED_OUT_KEY)
  } catch {
    // Nothing stored, or storage blocked.
  }
}

function sessionEndedElsewhere(error: AxiosError) {
  return (error.response?.data as { detail?: unknown } | undefined)?.detail === SESSION_ENDED
}

apiClient.interceptors.request.use((config) => {
  config.headers.set("X-Correlation-ID", createRequestId())
  const accessToken = getAccessToken()
  if (accessToken) config.headers.set("Authorization", `Bearer ${accessToken}`)
  return config
})

// A 401 means the access token aged out: mint a new one from the cookie and
// replay the original request once. Credential endpoints are excluded so a wrong
// password is reported to the form instead of looking like an expiry.
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined
    const expired =
      error.response?.status === 401 &&
      config !== undefined &&
      !config._retried &&
      !isCredentialRoute(config.url)

    if (!config || !expired) return Promise.reject(error)

    config._retried = true
    try {
      const accessToken = await refreshOnce()
      config.headers.set("Authorization", `Bearer ${accessToken}`)
      return await apiClient.request(config)
    } catch {
      // The session was ended by the server (a sign-in elsewhere, a password change), not
      // just expired: the sign-in page says so.
      endSession(sessionEndedElsewhere(error) ? "elsewhere" : undefined)
      return Promise.reject(error)
    }
  },
)

/** The HTTP status the server answered a failed request with, if it answered at all. */
export function apiErrorStatus(error: unknown) {
  return error instanceof AxiosError ? error.response?.status : undefined
}

export function apiErrorMessage(error: unknown) {
  if (error instanceof AxiosError) {
    const payload = error.response?.data as { detail?: unknown; message?: unknown; correlationId?: unknown } | undefined
    if (typeof payload?.message === "string") return payload.message
    // An error on our side carries the id of its log line: a short form of it to quote.
    if (typeof payload?.detail === "string" && typeof payload.correlationId === "string") return `${payload.detail} (ref ${payload.correlationId.slice(0, 8)})`
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

/** The answer was lost (a timeout or a dropped connection) or the server was briefly unavailable. */
export function isLostAnswer(error: unknown) {
  if (!(error instanceof AxiosError)) return false
  const status = error.response?.status
  return status === undefined || status === 502 || status === 503 || status === 504
}

/**
 * A mutation's `retry` for creates sent with an Idempotency-Key: twice more when the answer
 * was lost. The request may well have gone through; the key makes the retry return what it
 * created instead of creating it again.
 */
export function retryLostAnswer(failureCount: number, error: unknown) {
  return failureCount < 2 && isLostAnswer(error)
}
