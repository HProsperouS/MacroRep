import type { OverlayLayout } from "@/hooks/use-media-query"

/** Used by `vi.mock("@/hooks/use-media-query")`: the desktop layout, so pages render their side panels and dialogs. */

export const DESKTOP_QUERY = "(min-width: 1024px)"

export function useMediaQuery() {
  return true
}

export function useOverlayLayout(): OverlayLayout {
  return "dialog"
}
