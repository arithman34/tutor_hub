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

describe('layout', () => {
  it('opens every page from the sidebar without leaving the app', async () => {
    server.use(http.get('*/api/v1/calendar/status', () => HttpResponse.json({ connected: false })))
    const user = userEvent.setup()
    renderApp('/')
    const sidebar = await screen.findByRole('complementary', { name: 'Sidebar' })

    await user.click(within(sidebar).getByRole('link', { name: 'Connections' }))
    expect(await screen.findByRole('heading', { name: 'Connections' })).toBeInTheDocument()

    // Your name at the bottom of the sidebar opens your profile.
    await user.click(within(sidebar).getByRole('link', { name: 'Ada Lovelace' }))
    expect(await screen.findByRole('heading', { name: 'My profile' })).toBeInTheDocument()
    expect(within(sidebar).getByRole('link', { name: 'Ada Lovelace' })).toHaveAttribute('aria-current', 'page')
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

describe('demo account', () => {
  it('says the demo is made up and read-only', async () => {
    server.use(http.get('*/api/v1/auth/me', () => HttpResponse.json({ ...testUser, is_demo: true })))
    renderApp('/')
    expect(await screen.findByText(/looking round the demo/)).toHaveTextContent('nothing you change will be saved')
  })

  it('shows no banner to a real account', async () => {
    renderApp('/')
    // The sidebar shows the account's name once it has loaded.
    expect(await screen.findByRole('link', { name: 'Ada Lovelace' })).toBeInTheDocument()
    expect(screen.queryByText(/looking round the demo/)).not.toBeInTheDocument()
  })
})
