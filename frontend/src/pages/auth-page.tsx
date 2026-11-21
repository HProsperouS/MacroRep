import { LogOut } from "lucide-react"
import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { apiErrorMessage, forgetSignedOutReason, signedOutReason } from "@/api/client"
import { AuthForm, type AuthCredentials, type AuthMode } from "@/components/auth/auth-form"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useLogin, useRegister } from "@/hooks/use-auth"

const COPY: Record<AuthMode, { title: string; description: string; prompt: string; linkLabel: string; linkTo: string }> =
  {
    login: {
      title: "Sign in",
      description: "Your targets, log, and plan are waiting.",
      prompt: "New to MacroRep?",
      linkLabel: "Create an account",
      linkTo: "/register",
    },
    register: {
      title: "Create your account",
      description: "Set up in a few seconds — your coach does the rest.",
      prompt: "Already registered?",
      linkLabel: "Sign in",
      linkTo: "/login",
    },
  }

export default function AuthPage({ mode }: { mode: AuthMode }) {
  const navigate = useNavigate()
  const login = useLogin()
  const register = useRegister()
  const copy = COPY[mode]
  // Read once, then forgotten, so a later visit to the sign-in page doesn't repeat it.
  const [signedOutElsewhere] = useState(() => mode === "login" && signedOutReason() === "elsewhere")
  useEffect(() => forgetSignedOutReason(), [])

  const submit = (credentials: AuthCredentials) => {
    const handlers = {
      onSuccess: () => navigate("/", { replace: true }),
      onError: (error: unknown) =>
        toast.error(mode === "register" ? "Couldn’t create your account" : "Couldn’t sign you in", {
          description: apiErrorMessage(error),
        }),
    }
    if (mode === "register") register.mutate(credentials, handlers)
    else login.mutate({ email: credentials.email, password: credentials.password }, handlers)
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-background px-4 py-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <span className="font-display text-2xl font-semibold tracking-wide text-foreground">MACROREP</span>

        <Card>
          <CardHeader>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            {signedOutElsewhere ? (
              <Alert>
                <LogOut />
                <AlertTitle>You were signed out</AlertTitle>
                <AlertDescription>Your account was signed in on another device, or its password was changed. Sign in again to carry on here.</AlertDescription>
              </Alert>
            ) : null}
            <AuthForm mode={mode} submitting={login.isPending || register.isPending} onSubmit={submit} />
            {mode === "login" ? (
              <Link to="/forgot-password" className="-mt-2 text-sm font-medium text-primary hover:underline">
                Forgot password?
              </Link>
            ) : null}
            <p className="text-sm text-muted-foreground">
              {copy.prompt}{" "}
              <Link to={copy.linkTo} className="font-medium text-primary hover:underline">
                {copy.linkLabel}
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
