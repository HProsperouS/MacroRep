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

/** Asks for a code at `newEmail`; the sign-in email changes only once it's confirmed. */
export type RequestEmailChangeInput = {
  newEmail: string
  password: string
}

export type ConfirmEmailChangeInput = {
  code: string
}

/** The signed-in user, as `/users/me` and a confirmed email change return it. */
export type Me = {
  id: string
  name: string
  email: string
}
