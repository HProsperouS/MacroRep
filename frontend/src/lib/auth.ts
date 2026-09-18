/**
 * The only credential this app keeps in JavaScript: a short-lived access token,
 * held in memory so nothing survives the tab and no script can read it back later.
 *
 * The refresh token is deliberately absent. It lives in an httpOnly cookie that
 * the browser attaches to `/api/auth` and page scripts cannot see. The cost is
 * that the client can no longer answer "am I signed in?" by looking — it has to
 * ask the server, which is what `restoreSession` in `@/api/client` is for.
 */
let accessToken: string | null = null

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token: string) {
  accessToken = token
}

export function clearAccessToken() {
  accessToken = null
}
