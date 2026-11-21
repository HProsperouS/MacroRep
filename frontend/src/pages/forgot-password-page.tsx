import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { z } from "zod"

import { apiErrorMessage, apiErrorStatus } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { TextField } from "@/components/ui/text-field"
import { useConfirmPasswordReset, useRequestPasswordReset } from "@/hooks/use-auth"
import { NEW_PASSWORD_HINT, newPasswordPair } from "@/lib/password"

const emailSchema = z.object({ email: z.string().trim().min(1, "Enter your email").email("Enter a valid email") })
type EmailValues = z.infer<typeof emailSchema>

const resetSchema = z
  .object({
    code: z
      .string()
      .trim()
      .regex(/^\d{6}$/, "Enter the 6-digit code"),
  })
  .and(newPasswordPair)
type ResetValues = z.infer<typeof resetSchema>

/** Forgot password: an email gets a code, and the code sets a new password and signs in. */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState<string | null>(null)

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <span className="font-display text-2xl font-semibold tracking-wide text-foreground">MACROREP</span>

        <Card>
          <CardHeader>
            <CardTitle>Reset your password</CardTitle>
            <CardDescription>
              {email
                ? `If ${email} has an account, we sent it a code. It expires in 15 minutes.`
                : "Enter the email you sign in with and we’ll send you a code."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {email ? <ResetStep email={email} onBack={() => setEmail(null)} /> : <EmailStep onSent={setEmail} />}
            <p className="text-sm text-muted-foreground">
              Remembered it?{" "}
              <Link to="/login" className="font-medium text-primary hover:underline">
                Back to sign in
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function EmailStep({ onSent }: { onSent: (email: string) => void }) {
  const request = useRequestPasswordReset()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EmailValues>({ resolver: zodResolver(emailSchema), defaultValues: { email: "" } })

  const submit = handleSubmit(({ email }) =>
    request.mutate(
      { email },
      {
        onSuccess: () => onSent(email.trim().toLowerCase()),
        onError: (error) => toast.error("Couldn’t send a code", { description: apiErrorMessage(error) }),
      },
    ),
  )

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <TextField id="reset-email" label="Email" type="email" autoComplete="email" error={errors.email?.message} disabled={request.isPending} {...register("email")} />
      <Button type="submit" className="h-10 w-full" disabled={request.isPending}>
        {request.isPending ? <Spinner data-icon="inline-start" /> : null}
        Send code
      </Button>
    </form>
  )
}

function ResetStep({ email, onBack }: { email: string; onBack: () => void }) {
  const navigate = useNavigate()
  const confirm = useConfirmPasswordReset()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<ResetValues>({ resolver: zodResolver(resetSchema), defaultValues: { code: "", newPassword: "", repeatPassword: "" } })

  const submit = handleSubmit(({ code, newPassword }) =>
    confirm.mutate(
      { email, code, newPassword },
      {
        onSuccess: () => {
          toast.success("Password reset", { description: "You’re signed in. Other devices were signed out." })
          navigate("/", { replace: true })
        },
        onError: (error) => {
          const message = apiErrorMessage(error)
          if (apiErrorStatus(error) !== 422) toast.error("Couldn’t reset your password", { description: message })
          // The code is checked first, so any other refusal is about the new password.
          else if (/code/i.test(message)) setError("code", { message })
          else setError("newPassword", { message })
        },
      },
    ),
  )

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        <TextField
          id="reset-code"
          label="Code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          error={errors.code?.message}
          disabled={confirm.isPending}
          {...register("code")}
        />
        <TextField
          id="reset-new-password"
          label="New password"
          type="password"
          autoComplete="new-password"
          description={NEW_PASSWORD_HINT}
          error={errors.newPassword?.message}
          disabled={confirm.isPending}
          {...register("newPassword")}
        />
        <TextField
          id="reset-repeat-password"
          label="New password again"
          type="password"
          autoComplete="new-password"
          error={errors.repeatPassword?.message}
          disabled={confirm.isPending}
          {...register("repeatPassword")}
        />
      </FieldGroup>
      <Button type="submit" className="h-10 w-full" disabled={confirm.isPending}>
        {confirm.isPending ? <Spinner data-icon="inline-start" /> : null}
        Reset password
      </Button>
      <Button type="button" variant="ghost" className="h-10 w-full" onClick={onBack} disabled={confirm.isPending}>
        No code? Send a new one
      </Button>
    </form>
  )
}
