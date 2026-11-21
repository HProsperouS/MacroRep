import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { apiErrorMessage, apiErrorStatus as status } from "@/api/client"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { TextField } from "@/components/ui/text-field"
import { useCancelEmailChange, useConfirmEmailChange, useRequestEmailChange } from "@/hooks/use-auth"
import { useOverlayLayout } from "@/hooks/use-media-query"
import { submitOnly } from "@/lib/password"

const requestSchema = z.object({
  newEmail: z.string().trim().min(1, "Enter your new email").email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
})
type RequestValues = z.infer<typeof requestSchema>

const confirmSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^\d{6}$/, "Enter the 6-digit code"),
})
type ConfirmValues = z.infer<typeof confirmSchema>

type Step = { layout: OverlayLayout; newEmail: string | null } | null

/** The "Change" button beside the email, and the two steps it opens: new email and password, then the code
 * sent to it. The email only changes once the code is confirmed. */
export function ChangeEmail({ currentEmail, disabled = false }: { currentEmail: string; disabled?: boolean }) {
  const layout = useOverlayLayout()
  const [step, setStep] = useState<Step>(null)
  const cancel = useCancelEmailChange()

  function close() {
    // A code sent but not used is dropped; best effort, it expires on its own anyway.
    if (step?.newEmail) cancel.mutate()
    setStep(null)
  }

  return (
    <>
      <Button type="button" variant="outline" className="h-10" disabled={disabled} onClick={() => setStep({ layout, newEmail: null })}>
        Change
      </Button>
      <ResponsiveOverlay
        open={step !== null}
        onOpenChange={(open) => (open ? undefined : close())}
        layout={step?.layout ?? layout}
        title="Change email"
        description={step?.newEmail ? `Enter the code we sent to ${step.newEmail}.` : `You sign in with ${currentEmail}. We'll send a code to the new email to check it's yours.`}
      >
        {step?.newEmail ? (
          <ConfirmStep newEmail={step.newEmail} onBack={() => setStep({ layout: step.layout, newEmail: null })} onDone={() => setStep(null)} onCancel={close} />
        ) : step ? (
          <RequestStep onSent={(newEmail) => setStep({ layout: step.layout, newEmail })} onCancel={close} />
        ) : null}
      </ResponsiveOverlay>
    </>
  )
}

function RequestStep({ onSent, onCancel }: { onSent: (newEmail: string) => void; onCancel: () => void }) {
  const request = useRequestEmailChange()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RequestValues>({ resolver: zodResolver(requestSchema), defaultValues: { newEmail: "", password: "" } })

  const submit = handleSubmit((values) =>
    request.mutate(values, {
      onSuccess: () => onSent(values.newEmail.trim().toLowerCase()),
      onError: (error) => {
        const message = apiErrorMessage(error)
        if (status(error) === 403) setError("password", { message })
        else if (status(error) === 409 || status(error) === 422) setError("newEmail", { message })
        else toast.error("Couldn’t send the code", { description: message })
      },
    }),
  )

  return (
    <form onSubmit={submitOnly(submit)} noValidate className="flex flex-col gap-4">
      <TextField id="change-email-new" label="New email" type="email" autoComplete="email" error={errors.newEmail?.message} disabled={request.isPending} {...register("newEmail")} />
      <TextField
        id="change-email-password"
        label="Current password"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        disabled={request.isPending}
        {...register("password")}
      />
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={request.isPending}>
          Cancel
        </Button>
        <Button type="submit" className="h-10" disabled={request.isPending}>
          {request.isPending ? <Spinner data-icon="inline-start" /> : null}
          Send code
        </Button>
      </div>
    </form>
  )
}

function ConfirmStep({ newEmail, onBack, onDone, onCancel }: { newEmail: string; onBack: () => void; onDone: () => void; onCancel: () => void }) {
  const confirm = useConfirmEmailChange()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ConfirmValues>({ resolver: zodResolver(confirmSchema), defaultValues: { code: "" } })

  const submit = handleSubmit((values) =>
    confirm.mutate(values, {
      onSuccess: (me) => {
        toast.success("Email changed", { description: `Sign in with ${me.email} from now on.` })
        onDone()
      },
      onError: (error) => {
        const message = apiErrorMessage(error)
        if (status(error) === 422 || status(error) === 409) setError("code", { message })
        else toast.error("Couldn’t change your email", { description: message })
      },
    }),
  )

  return (
    <form onSubmit={submitOnly(submit)} noValidate className="flex flex-col gap-4">
      <TextField
        id="change-email-code"
        label="Code"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        description={`Sent to ${newEmail}. It expires in 15 minutes. No email? Go back to send a new one.`}
        error={errors.code?.message}
        disabled={confirm.isPending}
        {...register("code")}
      />
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="ghost" className="h-10" onClick={onBack} disabled={confirm.isPending}>
          Back
        </Button>
        <Button type="button" variant="outline" className="h-10" onClick={onCancel} disabled={confirm.isPending}>
          Cancel
        </Button>
        <Button type="submit" className="h-10" disabled={confirm.isPending}>
          {confirm.isPending ? <Spinner data-icon="inline-start" /> : null}
          Confirm
        </Button>
      </div>
    </form>
  )
}
