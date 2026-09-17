import { useState, type FormEvent } from "react"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { formatChangeValue } from "@/lib/format"
import type { Proposal } from "@/types/coach"

type EditProposalFormProps = {
  proposal: Proposal
  submitting: boolean
  onCancel: () => void
  onSubmit: (changes: { id: string; after: number }[]) => void
}

/** Edit the proposed values before applying. Mounted fresh per proposal (keyed by the caller). */
export function EditProposalForm({ proposal, submitting, onCancel, onSubmit }: EditProposalFormProps) {
  const [values, setValues] = useState(() => Object.fromEntries(proposal.changes.map((change) => [change.id, String(change.after)])))
  const [showErrors, setShowErrors] = useState(false)

  const errors = Object.fromEntries(
    proposal.changes.map((change) => {
      const raw = values[change.id]?.trim() ?? ""
      const value = Number(raw)
      if (raw === "" || !Number.isFinite(value)) return [change.id, "Enter a number"]
      if (value <= 0) return [change.id, "Must be greater than 0"]
      // The reviewer caps weekly changes; keep edits within ±25% of the current value here.
      if (Math.abs(value - change.before) > change.before * 0.25) return [change.id, `Stay within 25% of ${formatChangeValue(change.before, change.unit)}`]
      return [change.id, undefined]
    }),
  )
  const hasErrors = Object.values(errors).some(Boolean)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (hasErrors) {
      setShowErrors(true)
      return
    }
    onSubmit(proposal.changes.map((change) => ({ id: change.id, after: Number(values[change.id]) })))
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        {proposal.changes.map((change) => (
          <TextField
            key={change.id}
            id={`edit-${proposal.id}-${change.id}`}
            label={change.label}
            unit={change.unit}
            inputMode="decimal"
            step={change.step}
            value={values[change.id] ?? ""}
            onChange={(event) => setValues((prev) => ({ ...prev, [change.id]: event.target.value }))}
            description={`Now ${formatChangeValue(change.before, change.unit)} · proposed ${formatChangeValue(change.after, change.unit)}`}
            error={showErrors ? errors[change.id] : undefined}
            disabled={submitting}
          />
        ))}
      </FieldGroup>
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" className="h-10" disabled={submitting}>
          {submitting ? <Spinner data-icon="inline-start" /> : null}
          Apply edited values
        </Button>
      </div>
    </form>
  )
}
