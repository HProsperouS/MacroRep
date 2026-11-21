import type { FormEvent } from "react"
import { z } from "zod"

/** Mirrors the API's limits (`app/auth/schemas.py`), so they're stated before the round trip. The other
 * rules (not too common, not the email) are the server's, and come back as a field error. */
export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_LENGTH = 128

export const newPassword = z
  .string()
  .min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters`)
  .max(MAX_PASSWORD_LENGTH, `Keep it under ${MAX_PASSWORD_LENGTH} characters`)

export const NEW_PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters, and not a common one`

/** A new password typed twice. */
export const newPasswordPair = z
  .object({ newPassword, repeatPassword: z.string() })
  .refine((values) => values.newPassword === values.repeatPassword, { path: ["repeatPassword"], message: "The passwords don’t match" })

/** For a form in an overlay: it's portalled, but React still bubbles its submit to a form around the
 * button that opened it (the profile form). */
export function submitOnly(handler: (event: FormEvent<HTMLFormElement>) => Promise<void>) {
  return (event: FormEvent<HTMLFormElement>) => {
    event.stopPropagation()
    void handler(event)
  }
}
