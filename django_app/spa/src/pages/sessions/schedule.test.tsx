import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import type { CalendarSessionItem, Student } from '../../api/types'
import { renderApp } from '../../test/render'
import { server, testUser } from '../../test/server'

const sam: Student = {
  id: '22222222-2222-4222-8222-222222222222',
  payee_id: null,
  first_name: 'Sam',
  last_name: 'Smith',
  level: 'GCSE',
  hourly_rate: 30,
  zoom_meeting_id: null,
  google_doc_id: null,
  onedrive_shared_link: null,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}
const alex: Student = { ...sam, id: '33333333-3333-4333-8333-333333333333', first_name: 'Alex', last_name: 'Jones', is_active: false }

function event(): CalendarSessionItem {
  return {
    event_id: 'evt-1',
    summary: 'Sam - Tuition',
    student_name: 'Sam',
    date: '2026-12-01',
    start_time: '16:00',
    end_time: '17:00',
    all_day: false,
    html_link: '',
    logged: false,
    session_id: null,
    student_id: sam.id,
  }
}

/** Record what each booking endpoint receives. */
function serveBookings({ recurringCreated }: { recurringCreated?: number } = {}) {
  const sent: { oneOff: unknown[]; recurring: { day_configs: unknown[] }[] } = { oneOff: [], recurring: [] }
  server.use(
    http.post('*/api/v1/calendar/events', async ({ request }) => {
      sent.oneOff.push(await request.json())
      return HttpResponse.json(event(), { status: 201 })
    }),
    http.post('*/api/v1/calendar/events/recurring', async ({ request }) => {
      const body = (await request.json()) as { day_configs: unknown[] }
      sent.recurring.push(body)
      return HttpResponse.json(Array.from({ length: recurringCreated ?? body.day_configs.length }, event), { status: 201 })
    }),
    http.get('*/api/v1/calendar/sessions', () => HttpResponse.json({ items: [event()], error: null })),
  )
  return sent
}

beforeEach(() => {
  server.use(
    http.get('*/api/v1/auth/me', () => HttpResponse.json({ ...testUser, address: '1 High Street' })),
    http.get('*/api/v1/calendar/status', () => HttpResponse.json({ connected: true })),
    http.get('*/api/v1/students/', () => HttpResponse.json([sam, alex])),
  )
})

describe('scheduling a session', () => {
  it('books a one-off lesson for an active student and says so on the sessions list', async () => {
    const sent = serveBookings()
    const user = userEvent.setup()
    renderApp('/sessions/schedule')

    const student = await screen.findByLabelText('Student')
    // Inactive students can't be booked.
    expect(within(student).queryByRole('option', { name: 'Alex Jones' })).not.toBeInTheDocument()
    await user.selectOptions(student, 'Sam Smith')
    expect(screen.getByText('Sam - Tuition')).toBeInTheDocument()
    expect(screen.getByText(/Location: 1 High Street/)).toBeInTheDocument()

    await user.type(screen.getByLabelText('Date'), '2026-12-01')
    await user.click(screen.getByRole('button', { name: 'Add to Google Calendar' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Added to Google Calendar.')
    expect(screen.getByRole('heading', { name: 'Sessions' })).toBeInTheDocument()
    expect(sent.oneOff).toEqual([{ student_id: sam.id, date: '2026-12-01', start_time: '09:00', end_time: '10:00' }])
  })

  it('books weekly lessons on the chosen days', async () => {
    const sent = serveBookings()
    const user = userEvent.setup()
    renderApp('/sessions/schedule')

    await user.selectOptions(await screen.findByLabelText('Student'), 'Sam Smith')
    await user.click(screen.getByRole('button', { name: 'Weekly' }))
    await user.type(screen.getByLabelText('Starting from'), '2026-12-01')
    await user.click(screen.getByLabelText('No end date (repeats until you delete it)'))
    expect(screen.getByLabelText('Until')).toBeDisabled()
    await user.clear(screen.getByLabelText('Every … weeks'))
    await user.type(screen.getByLabelText('Every … weeks'), '2')

    await user.click(screen.getByLabelText('Tuesday'))
    await user.click(screen.getByLabelText('Thursday'))
    const thursdayStart = screen.getByLabelText('Thursday start')
    await user.clear(thursdayStart)
    await user.type(thursdayStart, '17:30')
    const thursdayEnd = screen.getByLabelText('Thursday end')
    await user.clear(thursdayEnd)
    await user.type(thursdayEnd, '18:30')
    await user.click(screen.getByRole('button', { name: 'Add to Google Calendar' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Added 2 weekly lessons to Google Calendar.')
    expect(sent.recurring).toEqual([
      {
        student_id: sam.id,
        start_date: '2026-12-01',
        end_date: null,
        interval_weeks: 2,
        day_configs: [
          { weekday: 1, start: '09:00', end: '10:00' },
          { weekday: 3, start: '17:30', end: '18:30' },
        ],
      },
    ])
  })

  it('checks a weekly booking before sending it', async () => {
    const sent = serveBookings()
    const user = userEvent.setup()
    renderApp('/sessions/schedule')

    await user.click(await screen.findByRole('button', { name: 'Weekly' }))
    await user.type(screen.getByLabelText('Starting from'), '2026-12-10')
    await user.type(screen.getByLabelText('Until'), '2026-12-01')
    await user.click(screen.getByRole('button', { name: 'Add to Google Calendar' }))

    expect(await screen.findByText('Choose a student')).toBeInTheDocument()
    expect(screen.getByText('Must be on or after the start date')).toBeInTheDocument()
    expect(screen.getByText('Choose at least one day')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Monday'))
    const mondayEnd = screen.getByLabelText('Monday end')
    await user.clear(mondayEnd)
    await user.type(mondayEnd, '08:00')
    await user.click(screen.getByRole('button', { name: 'Add to Google Calendar' }))

    expect(await screen.findByText('Monday: Must end after it starts')).toBeInTheDocument()
    expect(sent.recurring).toEqual([])
  })

  it('warns when Google only accepted some of a weekly booking', async () => {
    serveBookings({ recurringCreated: 1 })
    const user = userEvent.setup()
    renderApp('/sessions/schedule')

    await user.selectOptions(await screen.findByLabelText('Student'), 'Sam Smith')
    await user.click(screen.getByRole('button', { name: 'Weekly' }))
    await user.type(screen.getByLabelText('Starting from'), '2026-12-01')
    await user.click(screen.getByLabelText('No end date (repeats until you delete it)'))
    await user.click(screen.getByLabelText('Monday'))
    await user.click(screen.getByLabelText('Friday'))
    await user.click(screen.getByRole('button', { name: 'Add to Google Calendar' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Added 1 of 2 weekly lessons')
  })

  it('stays on the form with Google’s error when the booking fails', async () => {
    server.use(
      http.post('*/api/v1/calendar/events', () =>
        HttpResponse.json({ detail: "Google Calendar didn't accept the booking." }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderApp('/sessions/schedule')

    await user.selectOptions(await screen.findByLabelText('Student'), 'Sam Smith')
    await user.type(screen.getByLabelText('Date'), '2026-12-01')
    await user.click(screen.getByRole('button', { name: 'Add to Google Calendar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Google Calendar didn't accept the booking.")
    expect(screen.getByRole('heading', { name: 'Schedule session' })).toBeInTheDocument()
  })

  it('asks to connect Google first', async () => {
    server.use(http.get('*/api/v1/calendar/status', () => HttpResponse.json({ connected: false })))
    renderApp('/sessions/schedule')
    expect(await screen.findByRole('alert')).toHaveTextContent('Connect Google Calendar before scheduling sessions.')
    expect(screen.getByRole('link', { name: 'Go to Connections' })).toHaveAttribute('href', '/connections')
  })

  it('is reached from the sessions list', async () => {
    serveBookings()
    const user = userEvent.setup()
    renderApp('/sessions')
    await user.click(await screen.findByRole('link', { name: 'Schedule session' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Schedule session' })).toBeInTheDocument())
  })
})
