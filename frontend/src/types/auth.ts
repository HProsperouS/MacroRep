/** The body returned by register, login, and refresh. There is no refresh token
 * in it: that arrives separately, as an httpOnly cookie. */
export type AccessToken = {
  accessToken: string
}

export type RegisterInput = {
  name: string
  email: string
  password: string
}

export type LoginInput = {
  email: string
  password: string
}
