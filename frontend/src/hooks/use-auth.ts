import { useMutation, useQueryClient } from "@tanstack/react-query"

import { authApi } from "@/api/auth-api"
import { clearAccessToken, setAccessToken } from "@/lib/auth"
import type { LoginInput, RegisterInput } from "@/types/auth"

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
