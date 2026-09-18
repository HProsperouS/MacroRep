import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { TextField } from "@/components/food/form-field"
import { Button } from "@/components/ui/button"
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"

export type AuthMode = "login" | "register"

export type AuthCredentials = {
  name: string
  email: string
  password: string
}

/** Mirrors the API's minimum (`app/auth/schemas.py`), so the rule is stated before the round trip. */
const MIN_PASSWORD_LENGTH = 8

/** `name` is only collected when registering, so it is only required then. */
const authSchema = (mode: AuthMode) =>
  z
    .object({
      name: z.string().trim().max(60, "Keep it under 60 characters"),
      email: z.string().trim().min(1, "Enter your email").email("Enter a valid email"),
      password: z
        .string()
        .min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters`)
        .max(128, "Keep it under 128 characters"),
    })
    .refine((values) => mode === "login" || values.name.length > 0, {
      path: ["name"],
      message: "Enter your name",
    })

const SCHEMAS = { login: authSchema("login"), register: authSchema("register") }

type AuthValues = z.infer<ReturnType<typeof authSchema>>

type AuthFormProps = {
  mode: AuthMode
  submitting: boolean
  onSubmit: (credentials: AuthCredentials) => void
}

export function AuthForm({ mode, submitting, onSubmit }: AuthFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AuthValues>({
    resolver: zodResolver(SCHEMAS[mode]),
    defaultValues: { name: "", email: "", password: "" },
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-5">
      <FieldGroup>
        {mode === "register" ? (
          <TextField
            id="auth-name"
            label="Name"
            autoComplete="name"
            error={errors.name?.message}
            disabled={submitting}
            {...register("name")}
          />
        ) : null}
        <TextField
          id="auth-email"
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          disabled={submitting}
          {...register("email")}
        />
        <TextField
          id="auth-password"
          label="Password"
          type="password"
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          description={mode === "register" ? `At least ${MIN_PASSWORD_LENGTH} characters` : undefined}
          error={errors.password?.message}
          disabled={submitting}
          {...register("password")}
        />
      </FieldGroup>

      <Button type="submit" className="h-10 w-full" disabled={submitting}>
        {submitting ? <Spinner data-icon="inline-start" /> : null}
        {mode === "register" ? "Create account" : "Sign in"}
      </Button>
    </form>
  )
}
