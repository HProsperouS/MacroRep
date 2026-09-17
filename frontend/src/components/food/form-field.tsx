import type { ComponentProps } from "react"

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group"
import { cn } from "@/lib/utils"

type TextFieldProps = Omit<ComponentProps<"input">, "id"> & {
  id: string
  label: string
  error?: string
  description?: string
  /** Unit shown inside the input, e.g. "g" or "kcal". */
  unit?: string
  /** Theme colour class for a dot before the label, e.g. "bg-protein". */
  dotClassName?: string
}

/** Field + InputGroup composition used by the food forms. */
export function TextField({ id, label, error, description, unit, dotClassName, className, disabled, ...inputProps }: TextFieldProps) {
  const invalid = Boolean(error)
  const describedBy = error ? `${id}-error` : description ? `${id}-description` : undefined

  return (
    <Field data-invalid={invalid || undefined} data-disabled={disabled || undefined} className={cn("min-w-0", className)}>
      <FieldLabel htmlFor={id}>
        {dotClassName ? <span aria-hidden className={cn("size-2 rounded-full", dotClassName)} /> : null}
        {label}
      </FieldLabel>
      <InputGroup className="h-10">
        <InputGroupInput id={id} disabled={disabled} aria-invalid={invalid || undefined} aria-describedby={describedBy} {...inputProps} />
        {unit ? (
          <InputGroupAddon align="inline-end">
            <InputGroupText>{unit}</InputGroupText>
          </InputGroupAddon>
        ) : null}
      </InputGroup>
      {error ? (
        <FieldError id={`${id}-error`}>{error}</FieldError>
      ) : description ? (
        <FieldDescription id={`${id}-description`}>{description}</FieldDescription>
      ) : null}
    </Field>
  )
}
