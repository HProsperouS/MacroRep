import { useSyncExternalStore } from "react"

/**
 * One shared 1-second ticker for clocks and timers. Components that call this
 * re-render each second, so keep them small (e.g. the rest timer, not the whole session).
 */
const listeners = new Set<() => void>()
let timer: ReturnType<typeof setInterval> | undefined
let now = Date.now()

function subscribe(onTick: () => void) {
  listeners.add(onTick)
  if (!timer) {
    now = Date.now()
    timer = setInterval(() => {
      now = Date.now()
      listeners.forEach((listener) => listener())
    }, 1000)
  }
  return () => {
    listeners.delete(onTick)
    if (listeners.size === 0 && timer) {
      clearInterval(timer)
      timer = undefined
    }
  }
}

export function useNow() {
  return useSyncExternalStore(
    subscribe,
    () => now,
    () => now,
  )
}
