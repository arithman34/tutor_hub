import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CalendarSessionItem, Session, Student } from '../../api/types'
import { leaveFor } from '../../browser'
import { renderApp } from '../../test/render'
import { server, testUser } from '../../test/server'

vi.mock('../../browser')

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

function item(overrides: Partial<CalendarSessionItem> = {}): CalendarSessionItem {
  return {
    event_id: 'evt-1',
    summary: 'Sam Smith - Tuition',
    student_name: 'Sam Smith',
    date: '2026-03-05',
    start_time: '16:00',
    end_time: '17:00',
    all_day: false,
    html_link: 'https://calendar.google.com/event?eid=1',
    logged: false,
    session_id: null,
    student_id: sam.id,
    zoom_outcome: null,
    ...overrides,
  }
}

const SESSION_ID = '44444444-4444-4444-8444-444444444444'

function session(overrides: Partial<Session> = {}): Session {
  return {
    id: SESSION_ID,
    student: sam.id,
    // A late lesson in British Summer Time, stored as wall-clock UTC.
    session_date: '2026-07-14T23:30:00Z',
    session_start_time: '2026-07-14T23:30:00Z',
    session_end_time: '2026-07-14T23:55:00Z',
    minutes: 25,
    zoom_meeting_uuid: null,
    zoom_summary_raw: null,
    zoom_outcome: null,
    zoom_outcome_at: null,
    work_covered: 'Fractions',
    student_actions: null,
    tutor_actions: null,
    next_lesson_focus: 'Decimals',
    topic_tags: 'maths',
    is_no_show: false,
    calendar_event_id: null,
    calendar_recurring_id: null,
    calendar_html_link: null,
    ilp_generated_at: null,
    created_at: '2026-07-15T00:00:00Z',
    updated_at: '2026-07-15T00:00:00Z',
    ...overrides,
  }
}

function serveCalendar(items: CalendarSessionItem[], error: string | null = null) {
  const seen: URLSearchParams[] = []
  server.use(
    http.get('*/api/v1/calendar/sessions', ({ request }) => {
      seen.push(new URL(request.url).searchParams)
      return HttpResponse.json({ items, error })
    }),
  )
  return seen
}

beforeEach(() => {
  server.use(
    http.get('*/api/v1/students/', () => HttpResponse.json([sam, alex])),
    http.get('*/api/v1/sessions/:id/', ({ params }) =>
      params.id === SESSION_ID ? HttpResponse.json(session()) : HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
    ),
  )
})

describe('sessions list', () => {
  it('shows calendar events with their logged status and the right action', async () => {
    serveCalendar([
      item({ event_id: 'logged', logged: true, session_id: SESSION_ID }),
      item({ event_id: 'all-day', summary: 'Inset day', all_day: true, start_time: '', end_time: '', student_id: null }),
    ])
    renderApp('/sessions')

    const loggedRow = (await screen.findAllByText('Sam Smith - Tuition'))[0]!.closest('tr')!
    expect(within(loggedRow).getByText('05/03/2026')).toBeInTheDocument()
    expect(within(loggedRow).getByText('16:00 – 17:00')).toBeInTheDocument()
    expect(within(loggedRow).getByText('Logged')).toBeInTheDocument()
    expect(within(loggedRow).getByRole('link', { name: 'View' })).toHaveAttribute('href', `/sessions/${SESSION_ID}`)

    const allDayRow = screen.getByText('Inset day').closest('tr')!
    expect(within(allDayRow).getByText('All day')).toBeInTheDocument()
    expect(within(allDayRow).getByText('Not logged')).toBeInTheDocument()
  })

  it('links "Log session" to a form pre-filled from the event', async () => {
    serveCalendar([item()])
    renderApp('/sessions')

    const link = await screen.findByRole('link', { name: 'Log session' })
    const params = new URL(link.getAttribute('href')!, 'http://x').searchParams
    expect(Object.fromEntries(params)).toEqual({
      date: '2026-03-05',
      start_time: '16:00',
      end_time: '17:00',
      event_id: 'evt-1',
      html_link: 'https://calendar.google.com/event?eid=1',
      student_id: sam.id,
    })
  })

  it('filters by status and period on the server', async () => {
    const seen = serveCalendar([])
    const user = userEvent.setup()
    renderApp('/sessions')

    await user.click(await screen.findByRole('button', { name: 'Not logged' }))
    expect(await screen.findByText("No unlogged sessions. You're all caught up.")).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Future' }))

    await waitFor(() => expect(seen.at(-1)?.get('period')).toBe('future'))
    expect(seen.at(-1)?.get('status')).toBe('unlogged')
    expect(screen.getByRole('button', { name: 'Future' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('pages through long lists, 50 at a time', async () => {
    serveCalendar(Array.from({ length: 60 }, (_, index) => item({ event_id: `e${index}`, summary: `Lesson ${index + 1}` })))
    const user = userEvent.setup()
    renderApp('/sessions')

    expect(await screen.findByText('Showing 1–50 of 60')).toBeInTheDocument()
    expect(screen.queryByText('Lesson 51')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Showing 51–60 of 60')).toBeInTheDocument()
    expect(screen.getByText('Lesson 51')).toBeInTheDocument()
  })

  it('asks to connect Google Calendar when it never was', async () => {
    server.use(http.get('*/api/v1/calendar/sessions', () => HttpResponse.json({ detail: 'Not connected.' }, { status: 409 })))
    renderApp('/sessions')
    expect(await screen.findByRole('alert')).toHaveTextContent('Connect Google Calendar')
    expect(screen.getByRole('link', { name: 'Go to Connections' })).toHaveAttribute('href', '/connections')
  })

  it('shows Google errors, and reconnecting goes straight to Google', async () => {
    serveCalendar([], 'Google Calendar access expired. Please reconnect.')
    server.use(http.get('*/api/v1/calendar/connect', () => HttpResponse.json({ url: 'https://accounts.google.com/consent' })))
    const user = userEvent.setup()
    renderApp('/sessions')

    await user.click(await screen.findByRole('button', { name: 'Reconnect Google Calendar' }))
    await waitFor(() => expect(leaveFor).toHaveBeenCalledWith('https://accounts.google.com/consent'))
  })
})

describe('catching up with Zoom', () => {
  it('is only offered when Zoom is connected', async () => {
    serveCalendar([])
    renderApp('/sessions')
    expect(await screen.findByRole('link', { name: 'Schedule session' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Check Zoom for missed lessons' })).not.toBeInTheDocument()
  })

  it('logs missed lessons and refreshes the list', async () => {
    const seen = serveCalendar([])
    let sweeps = 0
    server.use(
      http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: true })),
      http.post('*/api/v1/zoom/sweep', () => {
        sweeps += 1
        return HttpResponse.json({
          logged: 1,
          no_shows: 1,
          notes_filled: 1,
          linked: 1,
          waiting: 0,
          failed: 0,
          sessions: [
            { session_id: 'new-1', student_name: 'Sam Smith', start: '2026-11-12T18:30:00Z', outcome: 'logged' },
            { session_id: 'old-1', student_name: 'Sam Smith', start: '2026-11-11T18:30:00Z', outcome: 'linked' },
          ],
        })
      }),
    )
    const user = userEvent.setup()
    renderApp('/sessions')

    await user.click(await screen.findByRole('button', { name: 'Check Zoom for missed lessons' }))
    const result = await screen.findByRole('status')
    expect(result).toHaveTextContent(
      "Zoom: logged 1 lesson, logged 1 no-show, filled notes on 1 session, matched 1 session you'd already written notes for.",
    )
    // Every session it touched is listed, with a link to check it.
    expect(within(result).getByRole('link', { name: 'Sam Smith, 12/11/2026 18:30' })).toHaveAttribute('href', '/sessions/new-1')
    expect(within(result).getByRole('link', { name: 'Sam Smith, 11/11/2026 18:30' })).toHaveAttribute('href', '/sessions/old-1')
    expect(result).toHaveTextContent('Linked, your notes kept')
    expect(sweeps).toBe(1)
    await waitFor(() => expect(seen.length).toBe(2))
  })

  it('says when there was nothing to log', async () => {
    serveCalendar([])
    server.use(
      http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: true })),
      http.post('*/api/v1/zoom/sweep', () =>
        HttpResponse.json({ logged: 0, no_shows: 0, notes_filled: 0, linked: 0, waiting: 0, failed: 0, sessions: [] }),
      ),
    )
    const user = userEvent.setup()
    renderApp('/sessions')
    await user.click(await screen.findByRole('button', { name: 'Check Zoom for missed lessons' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Zoom: nothing new to log.')
  })

  it('shows Zoom’s error', async () => {
    serveCalendar([])
    server.use(
      http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: true })),
      http.post('*/api/v1/zoom/sweep', () => HttpResponse.json({ detail: 'Your Zoom connection has expired.' }, { status: 409 })),
    )
    const user = userEvent.setup()
    renderApp('/sessions')
    await user.click(await screen.findByRole('button', { name: 'Check Zoom for missed lessons' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Your Zoom connection has expired.')
  })
})

describe('Zoom history', () => {
  it('marks sessions Zoom logged or filled on the list', async () => {
    serveCalendar([
      item({ event_id: 'a', logged: true, session_id: 'a1', zoom_outcome: 'notes_filled' }),
      item({ event_id: 'b', logged: true, session_id: 'b1', zoom_outcome: null }),
    ])
    renderApp('/sessions')
    const [, zoomRow, plainRow] = (await screen.findAllByRole('row')) as HTMLElement[]
    expect(within(zoomRow as HTMLElement).getByText('Zoom')).toBeInTheDocument()
    expect(within(zoomRow as HTMLElement).getByText(': Notes filled from Zoom')).toBeInTheDocument()
    expect(within(plainRow as HTMLElement).queryByText('Zoom')).not.toBeInTheDocument()
  })

  it('says on the session page what Zoom did', async () => {
    server.use(
      http.get('*/api/v1/sessions/:id/', () =>
        HttpResponse.json(session({ zoom_outcome: 'logged', zoom_outcome_at: '2026-11-13T09:15:00Z' })),
      ),
    )
    renderApp(`/sessions/${SESSION_ID}`)
    expect(await screen.findByText('Logged automatically from Zoom on 13/11/2026.')).toBeInTheDocument()
  })

  it('says nothing for a session Zoom never touched', async () => {
    renderApp(`/sessions/${SESSION_ID}`)
    expect(await screen.findByRole('heading', { name: 'Session notes' })).toBeInTheDocument()
    // (The "Fill from Zoom summary" button is always there; the history line isn't.)
    expect(screen.queryByText(/from Zoom on|Matched to its Zoom meeting/)).not.toBeInTheDocument()
  })
})

describe('logging a session', () => {
  it('pre-fills from the calendar event and saves wall-clock times', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/api/v1/sessions/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(session(), { status: 201 })
      }),
    )
    serveCalendar([])
    const user = userEvent.setup()
    renderApp(`/sessions/new?student_id=${sam.id}&date=2026-07-14&start_time=23:30&end_time=23:55&event_id=evt-1&html_link=https%3A%2F%2Fcal%2Fe1`)

    expect(await screen.findByText('Pre-filled from your Google Calendar event.')).toBeInTheDocument()
    expect(screen.getByLabelText('Student')).toHaveValue(sam.id)
    expect(screen.getByLabelText('Date')).toHaveValue('2026-07-14')

    await user.type(screen.getByLabelText('Work covered'), 'Fractions')
    await user.click(screen.getByRole('button', { name: 'Save session' }))

    expect(await screen.findByRole('heading', { name: 'Sessions' })).toBeInTheDocument()
    expect(body).toEqual({
      student: sam.id,
      session_date: '2026-07-14T23:30:00Z',
      session_start_time: '2026-07-14T23:30:00Z',
      session_end_time: '2026-07-14T23:55:00Z',
      is_no_show: false,
      work_covered: 'Fractions',
      student_actions: null,
      tutor_actions: null,
      next_lesson_focus: null,
      topic_tags: null,
      zoom_summary_raw: null,
      calendar_event_id: 'evt-1',
      calendar_html_link: 'https://cal/e1',
    })
  })

  it('checks the times before sending anything', async () => {
    let posted = false
    server.use(http.post('*/api/v1/sessions/', () => ((posted = true), HttpResponse.json(session(), { status: 201 }))))
    const user = userEvent.setup()
    renderApp(`/sessions/new?student_id=${sam.id}&date=2026-03-05&start_time=17:00&end_time=16:00`)

    await user.click(await screen.findByRole('button', { name: 'Save session' }))

    expect(await screen.findByText('Must be after the start time')).toBeInTheDocument()
    expect(posted).toBe(false)
  })

  it('fills the notes from a Zoom summary and keeps the original', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/api/v1/sessions/zoom-parse/', () =>
        HttpResponse.json({ work_covered: 'Long division', student_actions: '- worksheet', tutor_actions: '', next_lesson_focus: 'Fractions', topic_tags: 'division' }),
      ),
      http.post('*/api/v1/sessions/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(session(), { status: 201 })
      }),
    )
    serveCalendar([])
    const user = userEvent.setup()
    renderApp(`/sessions/new?student_id=${sam.id}&date=2026-03-05&start_time=16:00&end_time=17:00`)

    await user.click(await screen.findByRole('button', { name: 'Zoom summary' }))
    await user.type(screen.getByLabelText('Paste your Zoom AI summary'), 'We did long division.')
    await user.click(screen.getByRole('button', { name: 'Parse with AI' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Done')
    expect(screen.getByLabelText('Work covered')).toHaveValue('Long division')
    expect(screen.getByLabelText('Topic tags')).toHaveValue('division')

    await user.click(screen.getByRole('button', { name: 'Save session' }))
    await waitFor(() => expect(body).not.toBeNull())
    expect(body).toMatchObject({ work_covered: 'Long division', tutor_actions: null, zoom_summary_raw: 'We did long division.' })
  })

  it('says when the Zoom summary couldn’t be parsed', async () => {
    server.use(http.post('*/api/v1/sessions/zoom-parse/', () => HttpResponse.json({ detail: 'nope' }, { status: 502 })))
    const user = userEvent.setup()
    renderApp('/sessions/new')

    await user.click(await screen.findByRole('button', { name: 'Zoom summary' }))
    await user.type(screen.getByLabelText('Paste your Zoom AI summary'), 'text')
    await user.click(screen.getByRole('button', { name: 'Parse with AI' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't parse the summary")
  })

  it('saves a no-show without notes', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/api/v1/sessions/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(session({ is_no_show: true }), { status: 201 })
      }),
    )
    serveCalendar([])
    const user = userEvent.setup()
    renderApp(`/sessions/new?student_id=${sam.id}&date=2026-03-05&start_time=16:00&end_time=17:00`)

    await user.type(await screen.findByLabelText('Work covered'), 'typed before noticing')
    await user.click(screen.getByLabelText('Student did not show up'))
    expect(screen.queryByLabelText('Work covered')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save session' }))

    await waitFor(() => expect(body).not.toBeNull())
    expect(body).toMatchObject({ is_no_show: true, zoom_summary_raw: null })
    expect(body).not.toHaveProperty('work_covered')
  })
})

describe('session page', () => {
  it('shows the session at its wall-clock time, with notes', async () => {
    renderApp(`/sessions/${SESSION_ID}`)

    // 23:30Z in July is 00:30 the next day in London; it must still read 14 July, 23:30.
    expect(await screen.findByLabelText('Date')).toHaveValue('2026-07-14')
    expect(screen.getByLabelText('Start time')).toHaveValue('23:30')
    expect(screen.getByLabelText('End time')).toHaveValue('23:55')
    expect(screen.getByText('Duration: 25 min')).toBeInTheDocument()
    expect(screen.getByLabelText('Work covered')).toHaveValue('Fractions')
    expect(screen.getByRole('link', { name: 'Sam Smith' })).toHaveAttribute('href', `/students/${sam.id}`)
  })

  it('saves details without touching the notes, and notes without moving the session', async () => {
    const bodies: Record<string, unknown>[] = []
    server.use(
      http.patch('*/api/v1/sessions/:id/', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        bodies.push(body)
        return HttpResponse.json(session(body as Partial<Session>))
      }),
    )
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    const end = await screen.findByLabelText('End time')
    await user.clear(end)
    await user.type(end, '23:59')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(bodies).toHaveLength(1))

    await user.clear(screen.getByLabelText('Next lesson focus'))
    await user.click(screen.getByRole('button', { name: 'Save notes' }))
    await waitFor(() => expect(bodies).toHaveLength(2))

    expect(Object.keys(bodies[0]!).sort()).toEqual(['is_no_show', 'session_date', 'session_end_time', 'session_start_time', 'student'])
    expect(bodies[0]!.session_end_time).toBe('2026-07-14T23:59:00Z')
    expect(Object.keys(bodies[1]!).sort()).toEqual(['next_lesson_focus', 'student_actions', 'topic_tags', 'tutor_actions', 'work_covered'])
    expect(bodies[1]).toMatchObject({ next_lesson_focus: null, work_covered: 'Fractions' })
  })

  it('has no notes form for a no-show', async () => {
    server.use(http.get('*/api/v1/sessions/:id/', () => HttpResponse.json(session({ is_no_show: true }))))
    renderApp(`/sessions/${SESSION_ID}`)
    expect(await screen.findByText('No notes recorded. The student did not attend.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save notes' })).not.toBeInTheDocument()
  })

  it('has no separate Delete session button', async () => {
    renderApp(`/sessions/${SESSION_ID}`)
    expect(await screen.findByRole('button', { name: 'Clear notes' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete session' })).not.toBeInTheDocument()
  })

  it('clears a no-show after confirming', async () => {
    let deleted = false
    server.use(
      http.get('*/api/v1/sessions/:id/', () => HttpResponse.json(session({ is_no_show: true }))),
      http.delete('*/api/v1/sessions/:id/', () => ((deleted = true), new HttpResponse(null, { status: 204 }))),
    )
    serveCalendar([item({ logged: false })])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Clear session' }))

    expect(await screen.findByText('Session cleared. Its calendar event is back to Not logged.')).toBeInTheDocument()
    expect(deleted).toBe(true)
  })

  it('says so when the clear fails', async () => {
    server.use(http.delete('*/api/v1/sessions/:id/', () => new HttpResponse(null, { status: 500 })))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Clear notes' }))

    expect(await screen.findByText("Couldn't clear the session. Please try again.")).toBeInTheDocument()
  })

  it('clears the session after confirming, un-logging it', async () => {
    let deleted = false
    let patched = false
    server.use(
      http.delete('*/api/v1/sessions/:id/', () => ((deleted = true), new HttpResponse(null, { status: 204 }))),
      http.patch('*/api/v1/sessions/:id/', () => ((patched = true), HttpResponse.json(session()))),
    )
    serveCalendar([item({ logged: false })])
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Clear notes' }))

    expect(confirm.mock.calls[0]?.[0]).toMatch(/goes back to Not logged/)
    expect(await screen.findByRole('heading', { name: 'Sessions' })).toBeInTheDocument()
    expect(await screen.findByText('Session cleared. Its calendar event is back to Not logged.')).toBeInTheDocument()
    expect(deleted).toBe(true)
    // The whole record goes, not just the note fields.
    expect(patched).toBe(false)
  })

  it('keeps the session when the clear is cancelled', async () => {
    let deleted = false
    server.use(http.delete('*/api/v1/sessions/:id/', () => ((deleted = true), new HttpResponse(null, { status: 204 }))))
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Clear notes' }))

    expect(screen.getByLabelText('Work covered')).toHaveValue('Fractions')
    expect(deleted).toBe(false)
  })

  it('redoes the notes from the saved Zoom summary', async () => {
    server.use(
      http.get('*/api/v1/sessions/:id/', () => HttpResponse.json(session({ zoom_summary_raw: 'Original Zoom summary.' }))),
    )
    let parsedText: unknown = null
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/api/v1/sessions/zoom-parse/', async ({ request }) => {
        parsedText = ((await request.json()) as { summary: string }).summary
        return HttpResponse.json({ work_covered: 'Ratios', student_actions: '- worksheet', tutor_actions: '', next_lesson_focus: 'Percentages', topic_tags: 'ratio' })
      }),
      http.patch('*/api/v1/sessions/:id/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(session(body as Partial<Session>))
      }),
    )
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Fill from Zoom summary' }))
    expect(screen.getByLabelText('Paste your Zoom AI summary')).toHaveValue('Original Zoom summary.')

    await user.click(screen.getByRole('button', { name: 'Parse with AI' }))

    expect(await screen.findByDisplayValue('Ratios')).toBeInTheDocument()
    expect(screen.getByLabelText('Topic tags')).toHaveValue('ratio')
    expect(parsedText).toBe('Original Zoom summary.')

    await user.click(screen.getByRole('button', { name: 'Save notes' }))

    await waitFor(() => expect(body).not.toBeNull())
    expect(body).toEqual({
      work_covered: 'Ratios',
      student_actions: '- worksheet',
      tutor_actions: null,
      next_lesson_focus: 'Percentages',
      topic_tags: 'ratio',
      zoom_summary_raw: 'Original Zoom summary.',
    })
    // The panel closes once the new notes are saved.
    await waitFor(() => expect(screen.queryByLabelText('Paste your Zoom AI summary')).not.toBeInTheDocument())
  })

  it('fetches the summary from Zoom and saves it with its meeting', async () => {
    let parsedText: unknown = null
    let body: Record<string, unknown> | null = null
    server.use(
      http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: true })),
      http.get('*/api/v1/sessions/:id/zoom-summary/', () =>
        HttpResponse.json({ summary: 'Zoom says: fractions.', meeting_uuid: '/abc==' }),
      ),
      http.post('*/api/v1/sessions/zoom-parse/', async ({ request }) => {
        parsedText = ((await request.json()) as { summary: string }).summary
        return HttpResponse.json({ work_covered: 'Fractions again', student_actions: '', tutor_actions: '', next_lesson_focus: '', topic_tags: '' })
      }),
      http.patch('*/api/v1/sessions/:id/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(session(body as Partial<Session>))
      }),
    )
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Fill from Zoom summary' }))
    await user.click(await screen.findByRole('button', { name: 'Fetch from Zoom' }))

    expect(await screen.findByDisplayValue('Fractions again')).toBeInTheDocument()
    expect(screen.getByLabelText('Fetch or paste your Zoom AI summary')).toHaveValue('Zoom says: fractions.')
    expect(parsedText).toBe('Zoom says: fractions.')

    await user.click(screen.getByRole('button', { name: 'Save notes' }))
    await waitFor(() => expect(body).not.toBeNull())
    expect(body).toMatchObject({ zoom_summary_raw: 'Zoom says: fractions.', zoom_meeting_uuid: '/abc==' })
  })

  it('explains why Zoom had no summary', async () => {
    server.use(
      http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: true })),
      http.get('*/api/v1/sessions/:id/zoom-summary/', () =>
        HttpResponse.json({ detail: 'No Zoom meeting started within an hour of this session.' }, { status: 404 }),
      ),
    )
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Fill from Zoom summary' }))
    await user.click(await screen.findByRole('button', { name: 'Fetch from Zoom' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No Zoom meeting started within an hour')
  })

  it('offers only pasting when Zoom isn’t connected', async () => {
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Fill from Zoom summary' }))
    expect(screen.getByLabelText('Paste your Zoom AI summary')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fetch from Zoom' })).not.toBeInTheDocument()
  })

  it('saves a newly pasted summary with the notes it produced', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.post('*/api/v1/sessions/zoom-parse/', () =>
        HttpResponse.json({ work_covered: 'Algebra', student_actions: '', tutor_actions: '', next_lesson_focus: '', topic_tags: '' }),
      ),
      http.patch('*/api/v1/sessions/:id/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(session(body as Partial<Session>))
      }),
    )
    const user = userEvent.setup()
    renderApp(`/sessions/${SESSION_ID}`)

    await user.click(await screen.findByRole('button', { name: 'Fill from Zoom summary' }))
    expect(screen.getByLabelText('Paste your Zoom AI summary')).toHaveValue('')
    await user.type(screen.getByLabelText('Paste your Zoom AI summary'), 'A brand new summary.')
    await user.click(screen.getByRole('button', { name: 'Parse with AI' }))
    expect(await screen.findByDisplayValue('Algebra')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save notes' }))

    await waitFor(() => expect(body).not.toBeNull())
    expect(body).toMatchObject({ work_covered: 'Algebra', next_lesson_focus: null, zoom_summary_raw: 'A brand new summary.' })
  })

  it('explains a session that doesn’t exist', async () => {
    renderApp('/sessions/99999999-9999-4999-8999-999999999999')
    expect(await screen.findByRole('alert')).toHaveTextContent('doesn’t exist')
  })
})

describe('sessions page in the demo', () => {
  it('points to the students’ pages instead of asking to connect Google', async () => {
    server.use(
      http.get('*/api/v1/auth/me', () => HttpResponse.json({ ...testUser, is_demo: true })),
      http.get('*/api/v1/calendar/sessions', () => HttpResponse.json({ detail: 'Not connected.' }, { status: 409 })),
    )
    renderApp('/sessions')
    expect(await screen.findByText(/which the demo isn't linked to/)).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Students' })).toHaveAttribute('href', '/students')
    expect(screen.queryByRole('link', { name: 'Go to Connections' })).not.toBeInTheDocument()
  })
})
