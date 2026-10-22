import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"

/** Renders with a fresh query client that never retries, so a failed request surfaces at once. */
export function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return { queryClient, ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>) }
}

/** Renders a page inside a router at `url`, with a fresh query client. */
export function renderPage(page: ReactElement, url = "/") {
  return renderWithQuery(<MemoryRouter initialEntries={[url]}>{page}</MemoryRouter>)
}
