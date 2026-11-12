import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Payee, Session, Student } from '../../api/types'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'

const payee: Payee = {
  id: '11111111-1111-4111-8111-111111111111',
  first_name: 'Pat',
  last_name: 'Parent',
  email: null,
  phone_number: null,
  bank_reference_pattern: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} as Payee

function makeStudent(overrides: Partial<Student> = {}): Student {
  return {
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
    ...overrides,
  }
}

const sam = makeStudent()
const alex = makeStudent({ id: '33333333-3333-4333-8333-333333333333', first_name: 'Alex', last_name: 'Jones', level: null, hourly_rate: null, is_active: false })

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    id: '44444444-4444-4444-8444-444444444444',
    student: sam.id,
    session_date: '2026-03-05T16:00:00Z',
    session_start_time: '2026-03-05T16:00:00Z',
    session_end_time: '2026-03-05T17:00:00Z',
    minutes: 60,
    is_no_show: false,
    created_at: '2026-03-05T17:00:00Z',
    updated_at: '2026-03-05T17:00:00Z',
    ...overrides,
  } as Session
}

beforeEach(() => {
  server.use(
    http.get('*/api/v1/students/', () => HttpResponse.json([sam, alex])),
    http.get('*/api/v1/payees/', () => HttpResponse.json([payee])),
    http.get('*/api/v1/students/:id/', ({ params }) =>
      params.id === sam.id ? HttpResponse.json(sam) : HttpResponse.json({ detail: 'No Student matches the given query.' }, { status: 404 }),
    ),
    http.get('*/api/v1/sessions/', () => HttpResponse.json({ count: 0, next: null, previous: null, results: [] })),
  )
})

describe('students list', () => {
  it('shows each student with their level, rate and status', async () => {
    renderApp('/students')

    const samRow = (await screen.findByRole('link', { name: 'Sam Smith' })).closest('tr')!
    expect(within(samRow).getByText('GCSE')).toBeInTheDocument()
    expect(within(samRow).getByText('£30.00')).toBeInTheDocument()
    expect(within(samRow).getByText('Active')).toBeInTheDocument()

    const alexRow = screen.getByRole('link', { name: 'Alex Jones' }).closest('tr')!
    expect(within(alexRow).getAllByText('—')).toHaveLength(2)
    expect(within(alexRow).getByText('Inactive')).toBeInTheDocument()
  })

  it('searches by name on the server', async () => {
    let searched: string | null = null
    server.use(
      http.get('*/api/v1/students/', ({ request }) => {
        searched = new URL(request.url).searchParams.get('q')
        return HttpResponse.json(searched ? [sam] : [sam, alex])
      }),
    )
    const user = userEvent.setup()
    renderApp('/students')

    await user.type(await screen.findByLabelText('Search students'), 'sam')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('1 result for “sam”')).toBeInTheDocument()
    expect(searched).toBe('sam')
    expect(screen.queryByRole('link', { name: 'Alex Jones' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(await screen.findByRole('link', { name: 'Alex Jones' })).toBeInTheDocument()
  })

  it('says when there are no students yet', async () => {
    server.use(http.get('*/api/v1/students/', () => HttpResponse.json([])))
    renderApp('/students')
    expect(await screen.findByText('No students yet')).toBeInTheDocument()
  })
})

describe('adding a student', () => {
  it('checks the form before sending anything', async () => {
    let posted = false
    server.use(
      http.post('*/api/v1/students/', () => {
        posted = true
        return HttpResponse.json(sam, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/students/new')

    await user.type(await screen.findByLabelText('Hourly rate (£)'), 'thirty')
    await user.click(screen.getByRole('button', { name: 'Add student' }))

    expect(await screen.findByText('Enter a first name')).toBeInTheDocument()
    expect(screen.getByText('Enter a last name')).toBeInTheDocument()
    expect(screen.getByText('Enter an amount like 30 or 27.50')).toBeInTheDocument()
    expect(screen.getByLabelText('First name')).toHaveAttribute('aria-invalid', 'true')
    expect(posted).toBe(false)
  })

  it('creates the student and opens their page', async () => {
    let body: unknown = null
    server.use(
      http.post('*/api/v1/students/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(sam, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/students/new')

    await user.type(await screen.findByLabelText('First name'), '  sam ')
    await user.type(screen.getByLabelText('Last name'), 'smith')
    await user.type(screen.getByLabelText('Hourly rate (£)'), '27.50')
    await user.selectOptions(await screen.findByLabelText('Payee (optional)'), 'Pat Parent')
    await user.click(screen.getByRole('button', { name: 'Add student' }))

    expect(await screen.findByRole('heading', { name: /Sam Smith/ })).toBeInTheDocument()
    expect(body).toEqual({
      first_name: 'sam',
      last_name: 'smith',
      level: null,
      hourly_rate: 27.5,
      payee_id: payee.id,
      google_doc_id: null,
    })
  })

  it('shows the server’s validation errors on the right field', async () => {
    server.use(
      http.post('*/api/v1/students/', () =>
        HttpResponse.json({ payee_id: ['Invalid pk - object does not exist.'], non_field_errors: ['Something else.'] }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderApp('/students/new')

    await user.type(await screen.findByLabelText('First name'), 'Sam')
    await user.type(screen.getByLabelText('Last name'), 'Smith')
    await user.click(screen.getByRole('button', { name: 'Add student' }))

    expect(await screen.findByText('Invalid pk - object does not exist.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Something else.')
  })
})

describe('student page', () => {
  it('shows the student and their recent sessions', async () => {
    let askedFor: URLSearchParams | null = null
    server.use(
      http.get('*/api/v1/sessions/', ({ request }) => {
        askedFor = new URL(request.url).searchParams
        return HttpResponse.json({
          count: 2,
          next: null,
          previous: null,
          results: [makeSession(), makeSession({ id: '55555555-5555-4555-8555-555555555555', session_date: '2026-02-26T16:00:00Z', is_no_show: true })],
        })
      }),
    )
    renderApp(`/students/${sam.id}`)

    expect(await screen.findByLabelText('First name')).toHaveValue('Sam')
    expect(screen.getByLabelText('Hourly rate (£)')).toHaveValue('30')
    expect(await screen.findByText('05/03/2026')).toBeInTheDocument()
    expect(screen.getByText('60 min')).toBeInTheDocument()
    expect(screen.getByText('No-show')).toBeInTheDocument()
    expect(askedFor!.get('student')).toBe(sam.id)
    expect(screen.getByRole('link', { name: 'Log session' })).toHaveAttribute('href', `/sessions/new?student_id=${sam.id}`)
  })

  it('saves changes, including the ILP link as a document id', async () => {
    let body: Record<string, unknown> | null = null
    server.use(
      http.patch('*/api/v1/students/:id/', async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeStudent({ level: 'A-Level', google_doc_id: 'abc_123-XYZ' }))
      }),
    )
    const user = userEvent.setup()
    renderApp(`/students/${sam.id}`)

    const save = await screen.findByRole('button', { name: 'Save changes' })
    expect(save).toBeDisabled()

    await user.clear(screen.getByLabelText('Level'))
    await user.type(screen.getByLabelText('Level'), 'A-Level')
    await user.type(screen.getByLabelText('ILP document URL'), 'https://docs.google.com/document/d/abc_123-XYZ/edit')
    await user.click(save)

    expect(await screen.findByRole('status')).toHaveTextContent('Saved')
    expect(body).toMatchObject({ level: 'A-Level', google_doc_id: 'abc_123-XYZ', hourly_rate: 30 })
    expect(screen.getByRole('link', { name: 'Open ILP' })).toHaveAttribute('href', 'https://docs.google.com/document/d/abc_123-XYZ/')
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
  })

  it('rejects a link that isn’t a Google Doc', async () => {
    const user = userEvent.setup()
    renderApp(`/students/${sam.id}`)
    await user.type(await screen.findByLabelText('ILP document URL'), 'https://example.com/notes')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Paste a Google Docs link (…/document/d/…)')).toBeInTheDocument()
  })

  it('deactivates the student', async () => {
    server.use(http.post('*/api/v1/students/:id/toggle-active/', () => HttpResponse.json(makeStudent({ is_active: false }))))
    const user = userEvent.setup()
    renderApp(`/students/${sam.id}`)

    await user.click(await screen.findByRole('button', { name: 'Deactivate' }))

    expect(await screen.findByRole('button', { name: 'Activate' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Sam Smith/ })).toHaveTextContent('Inactive')
  })

  it('deletes only after confirming, then returns to the list', async () => {
    let deleted = false
    server.use(
      http.delete('*/api/v1/students/:id/', () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const user = userEvent.setup()
    renderApp(`/students/${sam.id}`)

    await user.click(await screen.findByRole('button', { name: 'Delete student' }))
    expect(deleted).toBe(false)

    await user.click(screen.getByRole('button', { name: 'Delete student' }))
    await waitFor(() => expect(deleted).toBe(true))
    expect(await screen.findByRole('heading', { name: 'Students' })).toBeInTheDocument()
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('also deletes their sessions'))
  })

  it('explains a student that doesn’t exist', async () => {
    renderApp(`/students/${alex.id}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('doesn’t exist')
  })
})
