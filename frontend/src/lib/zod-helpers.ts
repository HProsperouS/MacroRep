import { z } from "zod"

import { toNumber } from "@/lib/format"

/** Form strings → number; blank stays undefined (required error), junk becomes NaN (type error). */
export const formNumber = (value: unknown) => toNumber(value) ?? (value === "" || value == null ? undefined : Number.NaN)

export const requiredNumber = (label: string, min: number, max: number) =>
  z.preprocess(
    formNumber,
    z
      .number({ required_error: `Enter ${label}`, invalid_type_error: "Enter a number" })
      .min(min, `Must be at least ${min}`)
      .max(max, `Must be ${max.toLocaleString("en-SG")} or less`),
  )
