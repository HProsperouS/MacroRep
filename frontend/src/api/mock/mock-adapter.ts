import { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios"

import { createRequestId } from "@/api/client"
import type { CreateCustomFoodInput, CreateFoodEntryInput } from "@/api/food-api"
import { extraRoutes } from "@/api/mock/extra-routes"
import { db, type MockRoute } from "@/api/mock/mock-db"
import type { Food } from "@/types/food"

/**
 * In-memory stand-in for the FastAPI backend, plugged in as an axios adapter.
 * Requests still go through apiClient (interceptors, error handling), so
 * switching to the real API is a config change, not a code change.
 */

const LATENCY_MS = 350

const routes: MockRoute[] = [
  {
    method: "get",
    pattern: /^\/food-log$/,
    handler: ({ query }) => {
      const date = String(query.date ?? "")
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return [422, { detail: "date must be yyyy-MM-dd" }]
      const entries = (db.entries.get(date) ?? []).map(({ date: _date, ...entry }) => entry)
      return [200, { date, entries }]
    },
  },
  {
    method: "post",
    pattern: /^\/food-log\/entries$/,
    handler: ({ body }) => {
      const { date, ...entry } = body as CreateFoodEntryInput
      if (!entry.name || entry.calories < 0) return [422, { detail: "Invalid food entry" }]
      const created = { ...entry, id: createRequestId() }
      db.entries.set(date, [...(db.entries.get(date) ?? []), { ...created, date }])
      return [201, created]
    },
  },
  {
    method: "delete",
    pattern: /^\/food-log\/entries\/(?<id>[^/]+)$/,
    handler: ({ params }) => {
      for (const [date, entries] of db.entries) {
        if (entries.some((entry) => entry.id === params.id)) {
          db.entries.set(date, entries.filter((entry) => entry.id !== params.id))
          return [204]
        }
      }
      return [404, { detail: "Entry not found" }]
    },
  },
  {
    method: "get",
    pattern: /^\/foods$/,
    handler: ({ query }) => {
      const q = String(query.q ?? "").trim().toLowerCase()
      const limit = Number(query.limit ?? 8)
      const matches = q ? db.foods.filter((food) => `${food.name} ${food.brand ?? ""}`.toLowerCase().includes(q)) : db.foods
      return [200, matches.slice(0, limit)]
    },
  },
  {
    method: "post",
    pattern: /^\/foods$/,
    handler: ({ body }) => {
      const input = body as CreateCustomFoodInput
      if (!input.name?.trim()) return [422, { detail: "Food name is required" }]
      const created: Food = { ...input, id: createRequestId(), source: "custom" }
      db.foods = [created, ...db.foods]
      return [201, created]
    },
  },
  {
    method: "get",
    pattern: /^\/nutrition\/targets$/,
    handler: () => [200, db.targets],
  },
  ...extraRoutes,
]

function wait(ms: number, signal?: AbortSignal | { aborted?: boolean }) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    if (signal && "addEventListener" in signal) {
      signal.addEventListener("abort", () => {
        clearTimeout(timer)
        reject(new AxiosError("Request aborted", AxiosError.ERR_CANCELED))
      })
    }
  })
}

export async function mockAdapter(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  await wait(LATENCY_MS, config.signal)

  const method = (config.method ?? "get").toLowerCase()
  const path = (config.url ?? "").split("?")[0]
  const route = routes.find((r) => r.method === method && r.pattern.test(path))
  const match = route ? path.match(route.pattern) : null

  const [status, data] = route
    ? route.handler({
        params: (match?.groups ?? {}) as Record<string, string>,
        query: (config.params ?? {}) as Record<string, unknown>,
        body: typeof config.data === "string" ? JSON.parse(config.data) : config.data,
      })
    : [404, { detail: `No mock for ${method.toUpperCase()} ${path}` }]

  const response: AxiosResponse = {
    // Clone so cached query data never shares references with the mock db.
    data: data === undefined ? undefined : structuredClone(data),
    status,
    statusText: String(status),
    headers: new AxiosHeaders(),
    config,
    request: {},
  }

  if (status >= 400) {
    throw new AxiosError(`Request failed with status code ${status}`, status >= 500 ? AxiosError.ERR_BAD_RESPONSE : AxiosError.ERR_BAD_REQUEST, config, {}, response)
  }
  return response
}
