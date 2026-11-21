import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { apiErrorMessage, apiErrorStatus } from "@/api/client"
import { ResponsiveOverlay, type OverlayLayout } from "@/components/layout/responsive-overlay"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { TextField } from "@/components/ui/text-field"
import { useChangePassword } from "@/hooks/use-auth"
import { useOverlayLayout } from "@/hooks/use-media-query"
import { NEW_PASSWORD_HINT, newPasswordPair, submitOnly } from "@/lib/password"

const schema = z.object({ currentPassword: z.string().min(1, "Enter your current password") }).and(newPasswordPair)
type Values = z.infer<typeof schema>

/** The "Change" button beside the password, and the overlay it opens. Signs out every other device. */
export function ChangePassword({ disabled = false }: { disabled?: boolean }) {
  const layout = useOverlayLayout()
  const [openedWith, setOpenedWith] = useState<OverlayLayout | null>(null)
  const change = useChangePassword()
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { currentPassword: "", newPassword: "", repeatPassword: "" } })

  function close() {
    if (change.isPending) return
    reset()
    setOpenedWith(null)
  }

  const submit = handleSubmit(({ currentPassword, newPassword }) =>
    change.mutate(
      { currentPassword, newPassword },
      {
        onSuccess: () => {
          toast.success("Password changed", { description: "Your other devices are signed out." })
          reset()
          setOpenedWith(null)
        },
        onError: (error) => {
          const message = apiErrorMessage(error)
          if (apiErrorStatus(error) === 403) setError("currentPassword", { message })
          else if (apiErrorStatus(error) === 422) setError("newPassword", { message })
          else toast.error("Couldn’t change your password", { description: message })
        },
      },
    ),
  )

  return (
    <>
      <Button type="button" variant="outline" className="h-10" disabled={disabled} onClick={() => setOpenedWith(layout)}>
        Change
      </Button>
      <ResponsiveOverlay
        open={openedWith !== null}
        onOpenChange={(open) => (open ? undefined : close())}
        layout={openedWith ?? layout}
        title="Change password"
        description="Your other devices will be signed out."
      >
        <form onSubmit={submitOnly(submit)} noValidate className="flex flex-col gap-4">
          <TextField
            id="change-password-current"
            label="Current password"
            type="password"
            autoComplete="current-password"
            error={errors.currentPassword?.message}
            disabled={change.isPending}
            {...register("currentPassword")}
          />
          <TextField
            id="change-password-new"
            label="New password"
            type="password"
            autoComplete="new-password"
            description={NEW_PASSWORD_HINT}
            error={errors.newPassword?.message}
            disabled={change.isPending}
            {...register("newPassword")}
          />
          <TextField
            id="change-password-repeat"
            label="New password again"
            type="password"
            autoComplete="new-password"
            error={errors.repeatPassword?.message}
            disabled={change.isPending}
            {...register("repeatPassword")}
          />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" className="h-10" onClick={close} disabled={change.isPending}>
              Cancel
            </Button>
            <Button type="submit" className="h-10" disabled={change.isPending}>
              {change.isPending ? <Spinner data-icon="inline-start" /> : null}
              Change password
            </Button>
          </div>
        </form>
      </ResponsiveOverlay>
    </>
  )
}
