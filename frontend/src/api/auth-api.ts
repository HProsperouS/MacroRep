import { apiClient } from "@/api/client"
import type { AccessToken, LoginInput, RegisterInput } from "@/types/auth"

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
}
