import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server, testUser, unauthorized } from '../test/server'
import { ApiError, api, readCookie, unwrap } from './client'

describe('api client', () => {
  it('sends the CSRF token from the cookie on unsafe requests', async () => {
    document.cookie = 'csrftoken=from-cookie'
    let sent: string | null = null
    server.use(
      http.post('*/api/v1/auth/cookie/logout', ({ request }) => {
        sent = request.headers.get('X-CSRFToken')
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await api.POST('/api/v1/auth/cookie/logout')

    expect(sent).toBe('from-cookie')
  })

  it('fetches a CSRF token first when there is no cookie yet', async () => {
    let sent: string | null = null
    server.use(
      http.post('*/api/v1/auth/cookie/logout', ({ request }) => {
        sent = request.headers.get('X-CSRFToken')
        return new HttpResponse(null, { status: 204 })
      }),
    )

    await api.POST('/api/v1/auth/cookie/logout')

    expect(sent).toBe('test-csrf-token')
  })

  it('does not send a CSRF token on GET requests', async () => {
    document.cookie = 'csrftoken=from-cookie'
    let sent: string | null = 'unset'
    server.use(
      http.get('*/api/v1/auth/me', ({ request }) => {
        sent = request.headers.get('X-CSRFToken')
        return HttpResponse.json(testUser)
      }),
    )

    await api.GET('/api/v1/auth/me')

    expect(sent).toBeNull()
  })

  it('refreshes an expired login once and retries the request', async () => {
    let meCalls = 0
    let refreshCalls = 0
    server.use(
      http.get('*/api/v1/auth/me', () => (++meCalls === 1 ? unauthorized() : HttpResponse.json(testUser))),
      http.post('*/api/v1/auth/cookie/refresh', () => {
        refreshCalls++
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const result = await api.GET('/api/v1/auth/me')

    expect(result.data?.email).toBe(testUser.email)
    expect(refreshCalls).toBe(1)
    expect(meCalls).toBe(2)
  })

  it('retries a POST with its original body after refreshing', async () => {
    const bodies: unknown[] = []
    server.use(
      http.patch('*/api/v1/auth/me', async ({ request }) => {
        bodies.push(await request.json())
        return bodies.length === 1 ? unauthorized() : HttpResponse.json(testUser)
      }),
      http.post('*/api/v1/auth/cookie/refresh', () => new HttpResponse(null, { status: 204 })),
    )

    await api.PATCH('/api/v1/auth/me', { body: { first_name: 'Grace' } })

    expect(bodies).toEqual([{ first_name: 'Grace' }, { first_name: 'Grace' }])
  })

  it('shares one refresh between requests that expire together', async () => {
    let refreshCalls = 0
    const retried = new Set<string>()
    server.use(
      http.get('*/api/v1/auth/me', () => (retried.has('me') ? HttpResponse.json(testUser) : (retried.add('me'), unauthorized()))),
      http.get('*/api/v1/analytics/filters', () =>
        retried.has('filters') ? HttpResponse.json({ students: [], payees: [] }) : (retried.add('filters'), unauthorized()),
      ),
      http.post('*/api/v1/auth/cookie/refresh', async () => {
        refreshCalls++
        await new Promise((resolve) => setTimeout(resolve, 20))
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const [me, filters] = await Promise.all([api.GET('/api/v1/auth/me'), api.GET('/api/v1/analytics/filters')])

    expect(me.response.ok && filters.response.ok).toBe(true)
    expect(refreshCalls).toBe(1)
  })

  it('returns the 401 when the refresh fails too', async () => {
    server.use(http.get('*/api/v1/auth/me', unauthorized))

    const result = await api.GET('/api/v1/auth/me')

    expect(result.response.status).toBe(401)
  })

  it('never refreshes for the login call itself', async () => {
    let refreshCalls = 0
    server.use(
      http.post('*/api/v1/auth/cookie/login', unauthorized),
      http.post('*/api/v1/auth/cookie/refresh', () => {
        refreshCalls++
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const result = await api.POST('/api/v1/auth/cookie/login', { body: { email: 'a@b.c', password: 'x' } })

    expect(result.response.status).toBe(401)
    expect(refreshCalls).toBe(0)
  })
})

describe('unwrap', () => {
  it('throws an ApiError with Django’s detail message', async () => {
    server.use(http.get('*/api/v1/analytics/dashboard', () => HttpResponse.json({ detail: 'Nope.' }, { status: 403 })))

    const error = await api.GET('/api/v1/analytics/dashboard').then(unwrap, (e: unknown) => e).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(403)
    expect((error as ApiError).message).toBe('Nope.')
  })
})

describe('readCookie', () => {
  it('decodes values and ignores other cookies', () => {
    document.cookie = 'other=1'
    document.cookie = 'csrftoken=a%3Db'
    expect(readCookie('csrftoken')).toBe('a=b')
    expect(readCookie('missing')).toBeNull()
  })
})
