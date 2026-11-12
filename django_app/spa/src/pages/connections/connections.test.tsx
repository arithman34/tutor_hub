import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { leaveFor } from '../../browser'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'

vi.mock('../../browser')

function serveStatus(connected: boolean) {
  server.use(http.get('*/api/v1/calendar/status', () => HttpResponse.json({ connected })))
}

beforeEach(() => vi.mocked(leaveFor).mockClear())

describe('connections page', () => {
  it('connects by sending the browser to Google’s consent page', async () => {
    serveStatus(false)
    server.use(http.get('*/api/v1/calendar/connect', () => HttpResponse.json({ url: 'https://accounts.google.com/consent?state=s' })))
    const user = userEvent.setup()
    renderApp('/connections')

    expect(await screen.findByText('Not connected')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Connect' }))

    await waitFor(() => expect(leaveFor).toHaveBeenCalledWith('https://accounts.google.com/consent?state=s'))
    // The page stays put while the browser leaves, so the button can't be pressed twice.
    expect(screen.getByRole('button', { name: 'Opening Google…' })).toBeDisabled()
  })

  it('confirms a successful connection when Google sends the browser back', async () => {
    serveStatus(true)
    renderApp('/connections?connected=1')
    expect(await screen.findByRole('status')).toHaveTextContent('Google connected successfully.')
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('explains why connecting failed', async () => {
    serveStatus(false)
    renderApp('/connections?error=access_denied')
    expect(await screen.findByRole('alert')).toHaveTextContent('Google access was denied')
  })

  it('disconnects only after confirming, and clears the old success message', async () => {
    let connected = true
    let disconnects = 0
    server.use(
      http.get('*/api/v1/calendar/status', () => HttpResponse.json({ connected })),
      http.post('*/api/v1/calendar/disconnect', () => {
        disconnects += 1
        connected = false
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const user = userEvent.setup()
    renderApp('/connections?connected=1')

    await user.click(await screen.findByRole('button', { name: 'Disconnect' }))
    expect(confirm).toHaveBeenCalledTimes(1)
    expect(disconnects).toBe(0)

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(await screen.findByText('Not connected')).toBeInTheDocument()
    expect(disconnects).toBe(1)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
