import { apiClient } from "@/api/client"
import type {
  AccessToken,
  ChangePasswordInput,
  ConfirmEmailChangeInput,
  ConfirmPasswordResetInput,
  LoginInput,
  Me,
  RegisterInput,
  RequestEmailChangeInput,
  RequestPasswordResetInput,
} from "@/types/auth"

/** Refreshing is not here: the 401 interceptor in `@/api/client` owns it, and
 * the refresh token is a cookie this layer never sees. */
export const authApi = {
  async register(input: RegisterInput) {
    const { data } = await apiClient.post<AccessToken>("/auth/register", input)
    return data
  },

  async login(input: LoginInput) {
    const { data } = await apiClient.post<AccessToken>("/auth/login", input)
    return data
  },

  async logout() {
    await apiClient.post("/auth/logout")
  },

  async requestEmailChange(input: RequestEmailChangeInput) {
    await apiClient.post("/auth/email-change", input)
  },

  async confirmEmailChange(input: ConfirmEmailChangeInput) {
    const { data } = await apiClient.post<Me>("/auth/email-change/confirm", input)
    return data
  },

  async cancelEmailChange() {
    await apiClient.delete("/auth/email-change")
  },

  async changePassword(input: ChangePasswordInput) {
    const { data } = await apiClient.put<AccessToken>("/auth/password", input)
    return data
  },

  /** Answers the same whether or not the email has an account. */
  async requestPasswordReset(input: RequestPasswordResetInput) {
    await apiClient.post("/auth/password-reset", input)
  },

  async confirmPasswordReset(input: ConfirmPasswordResetInput) {
    const { data } = await apiClient.post<AccessToken>("/auth/password-reset/confirm", input)
    return data
  },
}
