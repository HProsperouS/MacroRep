import type { ComponentProps } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

type FormFieldProps = ComponentProps<"input"> & {
  id: string
  label: string
  error?: string
  hint?: string
  suffix?: string
  /** Tailwind bg class for a colour dot before the label, e.g. "bg-protein". */
  dotClassName?: string
  inputClassName?: string
}

export function FormField({
  id,
  label,
  error,
  hint,
  suffix,
  dotClassName,
  className,
  inputClassName,
  ...inputProps
}: FormFieldProps) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined

  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <Label htmlFor={id} className="gap-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        {dotClassName && <span className={cn("size-2 rounded-full", dotClassName)} aria-hidden />}
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn("h-11 rounded-xl bg-secondary px-3 text-base dark:bg-secondary", suffix && "pr-12", inputClassName)}
          {...inputProps}
        />
        {suffix && (
          <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  )
}
