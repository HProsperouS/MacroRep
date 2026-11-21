import { useMutation, useQueryClient } from "@tanstack/react-query"

import { authApi } from "@/api/auth-api"
import { profileKeys } from "@/api/query-keys"
import { clearAccessToken, setAccessToken } from "@/lib/auth"
import type {
  ChangePasswordInput,
  ConfirmEmailChangeInput,
  ConfirmPasswordResetInput,
  LoginInput,
  RegisterInput,
  RequestEmailChangeInput,
  RequestPasswordResetInput,
} from "@/types/auth"

/**
 * Signing in clears the cache: whatever is in it was fetched under the previous
 * session and must not be shown to the next one.
 */
export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: LoginInput) => authApi.login(input),
    onSuccess: (token) => {
      setAccessToken(token.accessToken)
      queryClient.clear()
    },
  })
}

export function useRegister() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: RegisterInput) => authApi.register(input),
    onSuccess: (token) => {
      setAccessToken(token.accessToken)
      queryClient.clear()
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    // Revoking server-side is best-effort; dropping the token locally is not.
    // A failed call must still leave the UI signed out.
    mutationFn: () => authApi.logout().catch(() => undefined),
    onSettled: () => {
      clearAccessToken()
      queryClient.clear()
    },
  })
}

/** Sends a code to the new email. Asking again sends a new code. */
export function useRequestEmailChange() {
  return useMutation({ mutationFn: (input: RequestEmailChangeInput) => authApi.requestEmailChange(input) })
}

export function useConfirmEmailChange() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ConfirmEmailChangeInput) => authApi.confirmEmailChange(input),
    // The profile shows the email.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: profileKeys.all }),
  })
}

export function useCancelEmailChange() {
  return useMutation({ mutationFn: () => authApi.cancelEmailChange() })
}

/** The answer is a new session for this device; the old one, on every other device, stops working. */
export function useChangePassword() {
  return useMutation({
    mutationFn: (input: ChangePasswordInput) => authApi.changePassword(input),
    onSuccess: (token) => setAccessToken(token.accessToken),
  })
}

export function useRequestPasswordReset() {
  return useMutation({ mutationFn: (input: RequestPasswordResetInput) => authApi.requestPasswordReset(input) })
}

/** Signs in, like `useLogin`. */
export function useConfirmPasswordReset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ConfirmPasswordResetInput) => authApi.confirmPasswordReset(input),
    onSuccess: (token) => {
      setAccessToken(token.accessToken)
      queryClient.clear()
    },
  })
}
