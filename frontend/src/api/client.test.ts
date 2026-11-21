import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { apiClient, apiErrorMessage, forgetSignedOutReason, restoreSession, retryLostAnswer, signedOutReason } from "@/api/client"
import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/auth"

const originalAdapter = apiClient.defaults.adapter
let requests: { url?: string; authorization: unknown; correlationId: unknown }[]

/** A fake server: only the "fresh" token is accepted; anything else is a 401. */
function fakeServer() {
  requests = []
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const authorization = config.headers.get("Authorization")
    requests.push({ url: config.url, authorization, correlationId: config.headers.get("X-Correlation-ID") })
    const response = { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config }
    if (config.url === "/auth/login" || authorization === "Bearer fresh") return response
    throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, { ...response, data: {}, status: 401, statusText: "Unauthorized" })
  }
}

function mockRefresh() {
  return vi.spyOn(axios, "post").mockResolvedValue({ data: { accessToken: "fresh" } })
}

beforeEach(() => {
  clearAccessToken()
  fakeServer()
  // Already on the login page, so ending a session doesn't try to navigate.
  window.history.pushState({}, "", "/login")
})

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
  clearAccessToken()
  forgetSignedOutReason()
})

describe("apiClient", () => {
  it("sends the access token and a correlation id", async () => {
    setAccessToken("fresh")
    await apiClient.get("/profile")
    expect(requests[0].authorization).toBe("Bearer fresh")
    expect(requests[0].correlationId).toEqual(expect.any(String))
  })

  it("refreshes an expired token once and replays the request", async () => {
    setAccessToken("stale")
    const refresh = mockRefresh()

    const response = await apiClient.get("/profile")

    expect(response.data).toEqual({ ok: true })
    expect(refresh).toHaveBeenCalledOnce()
    expect(refresh.mock.calls[0][0]).toMatch(/\/auth\/refresh$/)
    expect(requests.map((request) => request.authorization)).toEqual(["Bearer stale", "Bearer fresh"])
    expect(getAccessToken()).toBe("fresh")
  })

  it("shares one refresh between simultaneous expired requests", async () => {
    setAccessToken("stale")
    const refresh = mockRefresh()

    await Promise.all([apiClient.get("/profile"), apiClient.get("/food-log"), apiClient.get("/progress")])

    expect(refresh).toHaveBeenCalledOnce()
    expect(requests.filter((request) => request.authorization === "Bearer fresh")).toHaveLength(3)
  })

  it("ends the session when the refresh fails", async () => {
    setAccessToken("stale")
    vi.spyOn(axios, "post").mockRejectedValue(new Error("refresh cookie expired"))

    await expect(apiClient.get("/profile")).rejects.toMatchObject({ response: { status: 401 } })

    expect(getAccessToken()).toBeNull()
  })

  it("remembers a session ended elsewhere, for the sign-in page to explain", async () => {
    setAccessToken("stale")
    apiClient.defaults.adapter = async (config) => {
      throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, { data: { detail: "Session ended" }, status: 401, statusText: "Unauthorized", headers: {}, config })
    }
    vi.spyOn(axios, "post").mockRejectedValue(new Error("refresh cookie retired"))

    await expect(apiClient.get("/profile")).rejects.toMatchObject({ response: { status: 401 } })

    expect(signedOutReason()).toBe("elsewhere")
    forgetSignedOutReason()
    expect(signedOutReason()).toBeNull()
  })

  it("gives no reason when a session simply expired", async () => {
    setAccessToken("stale")
    vi.spyOn(axios, "post").mockRejectedValue(new Error("refresh cookie expired"))

    await expect(apiClient.get("/profile")).rejects.toMatchObject({ response: { status: 401 } })

    expect(signedOutReason()).toBeNull()
  })

  it("doesn't treat a wrong password as an expired token", async () => {
    apiClient.defaults.adapter = async (config) => {
      throw new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, { data: {}, status: 401, statusText: "Unauthorized", headers: {}, config })
    }
    const refresh = mockRefresh()

    await expect(apiClient.post("/auth/login", { email: "a@b.co", password: "wrong" })).rejects.toMatchObject({ response: { status: 401 } })

    expect(refresh).not.toHaveBeenCalled()
  })

  it("replays a request only once", async () => {
    setAccessToken("stale")
    vi.spyOn(axios, "post").mockResolvedValue({ data: { accessToken: "still-not-accepted" } })

    await expect(apiClient.get("/profile")).rejects.toMatchObject({ response: { status: 401 } })

    expect(requests).toHaveLength(2)
  })
})

describe("restoreSession", () => {
  it("is signed in without asking when a token is already held", async () => {
    setAccessToken("fresh")
    const refresh = mockRefresh()
    expect(await restoreSession()).toBe(true)
    expect(refresh).not.toHaveBeenCalled()
  })

  it("signs back in from the refresh cookie", async () => {
    mockRefresh()
    expect(await restoreSession()).toBe(true)
    expect(getAccessToken()).toBe("fresh")
  })

  it("reports signed out when there is no usable cookie", async () => {
    vi.spyOn(axios, "post").mockRejectedValue(new Error("401"))
    expect(await restoreSession()).toBe(false)
    expect(getAccessToken()).toBeNull()
  })
})

describe("apiErrorMessage", () => {
  const failure = (status: number, data: unknown) =>
    new AxiosError("failed", "ERR_BAD_REQUEST", undefined, null, { data, status, statusText: "", headers: {}, config: {} as InternalAxiosRequestConfig })

  it("prefers the server's message, then its detail", () => {
    expect(apiErrorMessage(failure(422, { message: "Calories too low", detail: [] }))).toBe("Calories too low")
    expect(apiErrorMessage(failure(404, { detail: "Workout not found" }))).toBe("Workout not found")
  })

  it("explains an unreachable server and a timeout", () => {
    expect(apiErrorMessage(new AxiosError("Network Error"))).toMatch(/could not reach the server/)
    expect(apiErrorMessage(new AxiosError("timeout", "ECONNABORTED"))).toMatch(/timed out/)
  })

  it("adds a short reference to an error on our side, to quote", () => {
    const failed = failure(500, { detail: "Something went wrong on our side. Try again in a moment.", correlationId: "3f9c2a7e-1b4d-4c8e" })
    expect(apiErrorMessage(failed)).toBe("Something went wrong on our side. Try again in a moment. (ref 3f9c2a7e)")
  })

  it("falls back to a generic message", () => {
    expect(apiErrorMessage(new Error("boom"))).toBe("Something went wrong. Please try again.")
    expect(apiErrorMessage(failure(500, "<html>"))).toBe("Something went wrong. Please try again.")
  })
})

describe("retryLostAnswer", () => {
  const answered = (status: number) =>
    new AxiosError("failed", "ERR_BAD_REQUEST", undefined, null, { data: {}, status, statusText: "", headers: {}, config: {} as InternalAxiosRequestConfig })

  it("retries a lost answer or a briefly unavailable server, twice", () => {
    expect(retryLostAnswer(0, new AxiosError("timeout", "ECONNABORTED"))).toBe(true)
    expect(retryLostAnswer(1, new AxiosError("Network Error"))).toBe(true)
    expect(retryLostAnswer(0, answered(503))).toBe(true)
    expect(retryLostAnswer(2, new AxiosError("Network Error"))).toBe(false)
  })

  it("doesn't retry an answer that refused the request", () => {
    expect(retryLostAnswer(0, answered(422))).toBe(false)
    expect(retryLostAnswer(0, answered(500))).toBe(false)
    expect(retryLostAnswer(0, new Error("boom"))).toBe(false)
  })
})
