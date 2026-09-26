import { format, isValid, parseISO } from "date-fns"

/** The yyyy-MM-dd key the API uses for a calendar day, in the user's local time. */
export function toDayKey(date: Date) {
  return format(date, "yyyy-MM-dd")
}

/** A real yyyy-MM-dd day that isn't in the future, by the user's local clock. */
export function isLoggableDay(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && isValid(parseISO(value)) && value <= toDayKey(new Date())
}
