import { useMediaQuery } from "@/hooks/use-media-query"

/** True below Tailwind's `md` breakpoint (768px) — matches the app shell's tab bar. */
export function useIsMobile() {
  return useMediaQuery("(max-width: 767px)")
}
