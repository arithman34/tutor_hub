import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '../../test/render'
import { server, testUser, unauthorized } from '../../test/server'

async function fillIn(user: ReturnType<typeof userEvent.setup>, confirm = 'a-long-secret') {
  await user.type(await screen.findByLabelText('First name'), 'ada')
  await user.type(screen.getByLabelText('Last name'), 'lovelace')
  await user.type(screen.getByLabelText('Email'), 'tutor@example.com')
  await user.type(screen.getByLabelText('Password'), 'a-long-secret')
  await user.type(screen.getByLabelText('Confirm password'), confirm)
}

describe('first-run setup', () => {
  it('sends a brand-new TutorHub to setup, creates the account and signs straight in', async () => {
    let signedIn = false
    let created: unknown = null
    let loginBody: unknown = null
    server.use(
      http.get('*/api/v1/auth/me', () => (signedIn ? HttpResponse.json(testUser) : unauthorized())),
      http.get('*/api/v1/setup', () => HttpResponse.json({ needed: created === null })),
      http.post('*/api/v1/setup', async ({ request }) => {
        created = await request.json()
        return HttpResponse.json(testUser, { status: 201 })
      }),
      http.post('*/api/v1/auth/cookie/login', async ({ request }) => {
        loginBody = await request.json()
        signedIn = true
        return HttpResponse.json(testUser)
      }),
    )
    const user = userEvent.setup()
    renderApp('/')

    expect(await screen.findByRole('heading', { name: 'Welcome to TutorHub' })).toBeInTheDocument()
    await fillIn(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Welcome back, Ada' })).toBeInTheDocument()
    // The confirmation is checked here, not sent.
    expect(created).toEqual({ first_name: 'ada', last_name: 'lovelace', email: 'tutor@example.com', password: 'a-long-secret' })
    expect(loginBody).toEqual({ email: 'tutor@example.com', password: 'a-long-secret' })
  })

  it('checks the passwords match and shows the server’s password rules', async () => {
    let attempts = 0
    server.use(
      http.get('*/api/v1/auth/me', unauthorized),
      http.get('*/api/v1/setup', () => HttpResponse.json({ needed: true })),
      http.post('*/api/v1/setup', () => {
        attempts += 1
        return HttpResponse.json({ password: ['This password is too common.'] }, { status: 400 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/setup')

    await fillIn(user, 'something-else')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText("Passwords don't match")).toBeInTheDocument()
    expect(attempts).toBe(0)

    await user.clear(screen.getByLabelText('Confirm password'))
    await user.type(screen.getByLabelText('Confirm password'), 'a-long-secret')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('This password is too common.')).toBeInTheDocument()
  })

  it('is closed once an account exists', async () => {
    server.use(http.get('*/api/v1/auth/me', unauthorized))
    renderApp('/setup')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })
})
