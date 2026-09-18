import { useSyncExternalStore } from "react"

import { getActiveWorkout, subscribeActiveWorkout } from "@/lib/active-workout-store"

/** The persisted in-progress workout, or null. Re-renders when it changes (in this or another tab). */
export function useActiveWorkout() {
  return useSyncExternalStore(subscribeActiveWorkout, getActiveWorkout, () => null)
}
