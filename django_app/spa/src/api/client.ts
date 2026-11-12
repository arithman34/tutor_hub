/**
 * The typed API client every page uses.
 *
 * `paths` is generated from Django's OpenAPI schema (npm run gen:api), so
 * api.GET('/api/v1/...') only accepts real endpoints, and their parameters,
 * request bodies and responses are all type-checked.
 *
 * Auth is the httponly JWT cookies set by POST /api/v1/auth/cookie/login.
 * JavaScript can't read them; the browser just sends them. On top of that,
 * this module:
 *   - adds the X-CSRFToken header Django requires on unsafe requests, and
 *   - when the 30-minute access token expires (a 401), refreshes the cookies
 *     once and retries the request, so the user isn't logged out mid-session.
 */
import createClient, { type Middleware } from 'openapi-fetch'

import type { paths } from './schema'

const CSRF_COOKIE = 'csrftoken'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS', 'TRACE'])

// Calls that must never trigger a refresh-and-retry: they're how you get
// (or give up) the cookies in the first place.
const NO_REFRESH_PATHS = ['/api/v1/auth/csrf', '/api/v1/auth/cookie/']

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(errorMessage(status, body))
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function errorMessage(status: number, body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
    return body.detail
  }
  return `Request failed (${status})`
}

/** An absolute URL on this site. (fetch outside a browser, as in tests, needs one.) */
function siteUrl(path: string): string {
  return new URL(path, window.location.origin).toString()
}

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [key, ...value] = part.trim().split('=')
    if (key === name) return decodeURIComponent(value.join('='))
  }
  return null
}

/** The CSRF token, fetching one first if this browser doesn't have it yet. */
async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) return existing
  const response = await fetch(siteUrl('/api/v1/auth/csrf'), { credentials: 'same-origin' })
  const body = (await response.json()) as { csrf_token: string }
  return body.csrf_token
}

// One refresh at a time: if five requests all hit a 401 together, they wait
// on the same refresh instead of rotating the refresh token five times.
let refreshInFlight: Promise<boolean> | null = null

function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(siteUrl('/api/v1/auth/cookie/refresh'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': await csrfToken() },
      })
      return response.ok
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

// A fetch() consumes a request's body, so keep an untouched copy to retry with.
const retryCopies = new WeakMap<Request, Request>()

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    if (!SAFE_METHODS.has(request.method)) {
      request.headers.set('X-CSRFToken', await csrfToken())
    }
    retryCopies.set(request, request.clone())
    return request
  },

  async onResponse({ request, response }) {
    const path = new URL(request.url).pathname
    if (response.status !== 401 || NO_REFRESH_PATHS.some((prefix) => path.startsWith(prefix))) {
      return response
    }

    const copy = retryCopies.get(request)
    if (!copy || !(await refreshSession())) return response
    return fetch(copy)
  },
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  // Look fetch up on every call rather than capturing it now, so test mocks
  // installed after this module loads still apply.
  fetch: (request) => globalThis.fetch(request),
})
api.use(authMiddleware)

/**
 * The data from an api.GET/POST/... result, or an ApiError with the status
 * and Django's error body. Lets pages write `unwrap(await api.GET(...))`
 * and handle failures in one place (React Query's `error`).
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok) return result.data as T
  throw new ApiError(result.response.status, result.error)
}
