import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from './test/render'
import { server, testUser, unauthorized } from './test/server'

describe('signing in', () => {
  it('sends logged-out visitors to the login page', async () => {
    server.use(http.get('*/api/v1/auth/me', unauthorized))
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('logs in and shows the dashboard', async () => {
    let loggedIn = false
    let sentBody: unknown = null
    server.use(
      http.get('*/api/v1/auth/me', () => (loggedIn ? HttpResponse.json(testUser) : unauthorized())),
      http.post('*/api/v1/auth/cookie/login', async ({ request }) => {
        sentBody = await request.json()
        loggedIn = true
        return HttpResponse.json(testUser)
      }),
    )
    const user = userEvent.setup()
    renderApp('/')

    await user.type(await screen.findByLabelText('Email'), 'tutor@example.com')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Welcome back, Ada' })).toBeInTheDocument()
    expect(sentBody).toEqual({ email: 'tutor@example.com', password: 'secret' })
  })

  it('shows an error for wrong credentials', async () => {
    server.use(
      http.get('*/api/v1/auth/me', unauthorized),
      http.post('*/api/v1/auth/cookie/login', () => HttpResponse.json({ detail: 'No active account' }, { status: 401 })),
    )
    const user = userEvent.setup()
    renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'tutor@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password')
  })

  it('skips the login page when already signed in', async () => {
    renderApp('/login')
    expect(await screen.findByRole('heading', { name: /Welcome back/ })).toBeInTheDocument()
  })

  it('signs out back to the login page', async () => {
    let loggedOut = false
    server.use(
      http.get('*/api/v1/auth/me', () => (loggedOut ? unauthorized() : HttpResponse.json(testUser))),
      http.post('*/api/v1/auth/cookie/logout', () => {
        loggedOut = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(loggedOut).toBe(true)
  })
})

describe('dashboard', () => {
  it('shows the headline numbers', async () => {
    renderApp('/')

    expect(await screen.findByText('£840.00')).toBeInTheDocument()
    expect(screen.getByText('+12.5% vs last month')).toBeInTheDocument()
    expect(screen.getByText('£12,345.50')).toBeInTheDocument()
    expect(screen.getByText('Nobody owes you anything')).toBeInTheDocument()
    expect(screen.getByText('21.5h')).toBeInTheDocument()
    expect(screen.getByText('-4% vs last month')).toBeInTheDocument()
  })

  it('says when it can’t load', async () => {
    server.use(http.get('*/api/v1/analytics/dashboard', () => HttpResponse.json({ detail: 'Forbidden.' }, { status: 403 })))
    renderApp('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Forbidden.')
  })
})

describe('layout', () => {
  it('links pages not yet rebuilt to the classic app', async () => {
    renderApp('/')
    const sidebar = await screen.findByRole('complementary', { name: 'Sidebar' })
    expect(within(sidebar).getByRole('link', { name: 'Connections' })).toHaveAttribute('href', '/connections')
    expect(within(sidebar).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/')
  })

  it('toggles and remembers dark mode', async () => {
    const user = userEvent.setup()
    renderApp('/')

    await user.click(await screen.findByRole('button', { name: 'Dark mode' }))

    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    expect(screen.getByRole('button', { name: 'Light mode' })).toBeInTheDocument()
  })

  it('shows a not-found page for unknown routes', async () => {
    renderApp('/no-such-page')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('reports when the server can’t be reached', async () => {
    server.use(http.get('*/api/v1/auth/me', () => HttpResponse.error()))
    renderApp('/')
    // A network error is retried once (after about a second) before giving up.
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent("Couldn't reach TutorHub"), { timeout: 4000 })
  })
})
