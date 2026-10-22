import { useCallback, useSyncExternalStore } from "react"

/** Subscribes to a CSS media query. One listener per query, no effect-driven state. */
export function useMediaQuery(query: string) {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const media = window.matchMedia(query)
      media.addEventListener("change", onChange)
      return () => media.removeEventListener("change", onChange)
    },
    [query],
  )
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  )
}

/** Tailwind `lg` breakpoint (1024px): side panels and dialogs instead of drawers. */
export const DESKTOP_QUERY = "(min-width: 1024px)"

/** A dialog on desktop, a bottom drawer below (handoff §7). */
export type OverlayLayout = "dialog" | "drawer"

/** The overlay to open now: a dialog on desktop, a drawer below. Read it when opening and keep it. */
export function useOverlayLayout(): OverlayLayout {
  return useMediaQuery(DESKTOP_QUERY) ? "dialog" : "drawer"
}
