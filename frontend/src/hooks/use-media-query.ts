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
