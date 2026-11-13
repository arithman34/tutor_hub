import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { leaveFor } from '../../browser'
import { renderApp } from '../../test/render'
import { server, testUser } from '../../test/server'

vi.mock('../../browser')

function serveStatus(connected: boolean) {
  server.use(http.get('*/api/v1/calendar/status', () => HttpResponse.json({ connected })))
}

function serveZoomStatus(connected: boolean) {
  server.use(http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected })))
}

const googleCard = () => screen.findByRole('region', { name: 'Google Calendar' })
const zoomCard = () => screen.findByRole('region', { name: 'Zoom' })

beforeEach(() => vi.mocked(leaveFor).mockClear())

describe('connections page', () => {
  it('connects by sending the browser to Google’s consent page', async () => {
    serveStatus(false)
    server.use(http.get('*/api/v1/calendar/connect', () => HttpResponse.json({ url: 'https://accounts.google.com/consent?state=s' })))
    const user = userEvent.setup()
    renderApp('/connections')

    const card = await googleCard()
    expect(await within(card).findByText('Not connected')).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: 'Connect' }))

    await waitFor(() => expect(leaveFor).toHaveBeenCalledWith('https://accounts.google.com/consent?state=s'))
    // The page stays put while the browser leaves, so the button can't be pressed twice.
    expect(within(card).getByRole('button', { name: 'Opening Google…' })).toBeDisabled()
  })

  it('confirms a successful connection when Google sends the browser back', async () => {
    serveStatus(true)
    renderApp('/connections?connected=1')
    expect(await screen.findByRole('status')).toHaveTextContent('Google connected successfully.')
    expect(within(await googleCard()).getByText('Connected')).toBeInTheDocument()
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

    const card = await googleCard()
    await user.click(await within(card).findByRole('button', { name: 'Disconnect' }))
    expect(confirm).toHaveBeenCalledTimes(1)
    expect(disconnects).toBe(0)

    await user.click(within(card).getByRole('button', { name: 'Disconnect' }))
    expect(await within(card).findByText('Not connected')).toBeInTheDocument()
    expect(disconnects).toBe(1)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('connecting Zoom', () => {
  beforeEach(() => serveStatus(false))

  it('connects by sending the browser to Zoom’s consent page', async () => {
    server.use(http.get('*/api/v1/zoom/connect', () => HttpResponse.json({ url: 'https://zoom.us/oauth/authorize?state=s' })))
    const user = userEvent.setup()
    renderApp('/connections')

    const card = await zoomCard()
    await user.click(await within(card).findByRole('button', { name: 'Connect' }))

    await waitFor(() => expect(leaveFor).toHaveBeenCalledWith('https://zoom.us/oauth/authorize?state=s'))
    expect(within(card).getByRole('button', { name: 'Opening Zoom…' })).toBeDisabled()
  })

  it('confirms a successful connection when Zoom sends the browser back', async () => {
    serveZoomStatus(true)
    renderApp('/connections?provider=zoom&connected=1')
    expect(await screen.findByRole('status')).toHaveTextContent('Zoom connected successfully.')
    expect(within(await zoomCard()).getByText('Connected')).toBeInTheDocument()
    expect(within(await googleCard()).getByText('Not connected')).toBeInTheDocument()
  })

  it('names Zoom when connecting it failed', async () => {
    renderApp('/connections?provider=zoom&error=access_denied')
    expect(await screen.findByRole('alert')).toHaveTextContent('Zoom access was denied')
  })

  it('disconnects after confirming', async () => {
    let connected = true
    server.use(
      http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected })),
      http.post('*/api/v1/zoom/disconnect', () => {
        connected = false
        return new HttpResponse(null, { status: 204 })
      }),
    )
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true)
    const user = userEvent.setup()
    renderApp('/connections')

    const card = await zoomCard()
    await user.click(await within(card).findByRole('button', { name: 'Disconnect' }))
    expect(await within(card).findByText('Not connected')).toBeInTheDocument()
  })
})

describe('connections page in the demo', () => {
  it('offers no way to connect Google or Zoom', async () => {
    server.use(http.get('*/api/v1/auth/me', () => HttpResponse.json({ ...testUser, is_demo: true })))
    serveStatus(false)
    renderApp('/connections')
    await waitFor(() => expect(screen.getAllByText('Not available in the demo.')).toHaveLength(2))
    expect(screen.queryByRole('button', { name: 'Connect' })).not.toBeInTheDocument()
  })
})
