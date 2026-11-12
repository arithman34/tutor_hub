import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '../../test/render'
import { server, testUser } from '../../test/server'

describe('profile page', () => {
  it('saves your details, and the sidebar shows the new name', async () => {
    let sent: unknown = null
    server.use(
      http.patch('*/api/v1/auth/me', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ ...testUser, first_name: 'Augusta', address: '1 High Street' })
      }),
    )
    const user = userEvent.setup()
    renderApp('/profile')

    const firstName = await screen.findByLabelText('First name')
    expect(firstName).toHaveValue('Ada')
    await user.clear(firstName)
    await user.type(firstName, 'Augusta')
    await user.type(screen.getByLabelText('Tutoring address (optional)'), '1 High Street')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Profile updated.')
    expect(sent).toEqual({ first_name: 'Augusta', last_name: 'Lovelace', email: 'tutor@example.com', address: '1 High Street' })
    const sidebar = screen.getByRole('complementary', { name: 'Sidebar' })
    expect(within(sidebar).getByRole('link', { name: 'Augusta Lovelace' })).toBeInTheDocument()
  })

  it('shows the server’s reason next to the field', async () => {
    server.use(
      http.patch('*/api/v1/auth/me', () => HttpResponse.json({ email: ['An account with this email already exists.'] }, { status: 400 })),
    )
    const user = userEvent.setup()
    renderApp('/profile')

    const email = await screen.findByLabelText('Email')
    await user.clear(email)
    await user.type(email, 'taken@example.com')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('An account with this email already exists.')).toBeInTheDocument()
    expect(email).toHaveAttribute('aria-invalid', 'true')
  })

  it('changes your password, checking the confirmation first', async () => {
    const sent: unknown[] = []
    server.use(
      http.post('*/api/v1/auth/password', async ({ request }) => {
        sent.push(await request.json())
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/profile')

    await user.type(await screen.findByLabelText('Current password'), 'old-secret')
    await user.type(screen.getByLabelText('New password'), 'a-new-secret')
    await user.type(screen.getByLabelText('Confirm new password'), 'a-typo')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText("Passwords don't match")).toBeInTheDocument()
    expect(sent).toEqual([])

    await user.clear(screen.getByLabelText('Confirm new password'))
    await user.type(screen.getByLabelText('Confirm new password'), 'a-new-secret')
    await user.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Password changed.')
    expect(sent).toEqual([{ current_password: 'old-secret', new_password: 'a-new-secret' }])
    expect(screen.getByLabelText('Current password')).toHaveValue('')
  })

  it('says when the current password is wrong', async () => {
    server.use(
      http.post('*/api/v1/auth/password', () => HttpResponse.json({ current_password: ['Current password is incorrect.'] }, { status: 400 })),
    )
    const user = userEvent.setup()
    renderApp('/profile')

    await user.type(await screen.findByLabelText('Current password'), 'wrong')
    await user.type(screen.getByLabelText('New password'), 'a-new-secret')
    await user.type(screen.getByLabelText('Confirm new password'), 'a-new-secret')
    await user.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Current password is incorrect.')).toBeInTheDocument()
  })
})
