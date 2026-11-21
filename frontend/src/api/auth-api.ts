import { apiClient } from "@/api/client"
import type { AccessToken, ConfirmEmailChangeInput, LoginInput, Me, RegisterInput, RequestEmailChangeInput } from "@/types/auth"

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
}
