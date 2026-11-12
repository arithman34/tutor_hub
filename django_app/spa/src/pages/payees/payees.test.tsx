import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Payee, Payment, Student } from '../../api/types'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'

function makePayee(overrides: Partial<Payee> = {}): Payee {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    first_name: 'Pat',
    last_name: 'Parent',
    email: 'pat@example.com',
    phone_number: null,
    bank_reference_pattern: 'PARENT-SAM',
    balance: -20,
    student_count: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const pat = makePayee()
const lee = makePayee({ id: '55555555-5555-4555-8555-555555555555', first_name: 'Lee', last_name: 'Lender', email: null, bank_reference_pattern: null, balance: 15, student_count: 0 })
const sue = makePayee({ id: '66666666-6666-4666-8666-666666666666', first_name: 'Sue', last_name: 'Settled', balance: 0, student_count: 2 })

const sam = {
  id: '22222222-2222-4222-8222-222222222222',
  payee_id: pat.id,
  first_name: 'Sam',
  last_name: 'Smith',
  level: 'GCSE',
  hourly_rate: 30,
  is_active: true,
} as Student

function payment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: '77777777-7777-4777-8777-777777777777',
    payee: pat.id,
    payee_name: 'Pat Parent',
    amount: '40.00',
    payment_date: '2026-03-06T00:00:00Z',
    payment_reference: 'FT123',
    created_at: '2026-03-06T00:00:00Z',
    updated_at: '2026-03-06T00:00:00Z',
    ...overrides,
  }
}

beforeEach(() => {
  server.use(
    http.get('*/api/v1/payees/', () => HttpResponse.json([pat, lee, sue])),
    http.get('*/api/v1/payees/:id/', ({ params }) =>
      params.id === pat.id ? HttpResponse.json(pat) : HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
    ),
    http.get('*/api/v1/students/', () => HttpResponse.json([sam])),
    http.get('*/api/v1/payments/', () => HttpResponse.json({ count: 1, next: null, previous: null, results: [payment()] })),
  )
})

describe('payees list', () => {
  it('shows each payee with a signed, coloured balance', async () => {
    renderApp('/payees')

    const patRow = (await screen.findByRole('link', { name: 'Pat Parent' })).closest('tr')!
    expect(within(patRow).getByText('-£20.00')).toHaveClass('text-red-600')
    expect(within(patRow).getByText('PARENT-SAM')).toBeInTheDocument()
    expect(within(patRow).getByText('1')).toBeInTheDocument()

    const leeRow = screen.getByRole('link', { name: 'Lee Lender' }).closest('tr')!
    expect(within(leeRow).getByText('+£15.00')).toHaveClass('text-green-600')

    const sueRow = screen.getByRole('link', { name: 'Sue Settled' }).closest('tr')!
    expect(within(sueRow).getByText('+£0.00')).toHaveClass('text-gray-500')
  })

  it('searches by name on the server', async () => {
    let searched: string | null = null
    server.use(
      http.get('*/api/v1/payees/', ({ request }) => {
        searched = new URL(request.url).searchParams.get('q')
        return HttpResponse.json(searched ? [pat] : [pat, lee, sue])
      }),
    )
    const user = userEvent.setup()
    renderApp('/payees')

    await user.type(await screen.findByLabelText('Search payees'), 'pat')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => expect(screen.queryByRole('link', { name: 'Lee Lender' })).not.toBeInTheDocument())
    expect(searched).toBe('pat')
  })
})

describe('adding a payee', () => {
  it('checks the email and sends blanks as null', async () => {
    let body: unknown = null
    server.use(
      http.post('*/api/v1/payees/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(pat, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/payees/new')

    await user.type(await screen.findByLabelText('First name'), 'Pat')
    await user.type(screen.getByLabelText('Last name'), 'Parent')
    await user.type(screen.getByLabelText('Email (optional)'), 'not-an-email')
    await user.click(screen.getByRole('button', { name: 'Add payee' }))
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(body).toBeNull()

    await user.clear(screen.getByLabelText('Email (optional)'))
    await user.click(screen.getByRole('button', { name: 'Add payee' }))

    expect(await screen.findByRole('heading', { name: 'Pat Parent' })).toBeInTheDocument()
    expect(body).toEqual({ first_name: 'Pat', last_name: 'Parent', email: null, phone_number: null, bank_reference_pattern: null })
  })
})

describe('payee page', () => {
  it('shows the balance, linked students and payment history', async () => {
    const asked: Record<string, string | null> = {}
    server.use(
      http.get('*/api/v1/students/', ({ request }) => {
        asked.students = new URL(request.url).searchParams.get('payee')
        return HttpResponse.json([sam])
      }),
      http.get('*/api/v1/payments/', ({ request }) => {
        asked.payments = new URL(request.url).searchParams.get('payee')
        return HttpResponse.json({ count: 1, next: null, previous: null, results: [payment()] })
      }),
    )
    renderApp(`/payees/${pat.id}`)

    const balance = await screen.findByRole('region', { name: 'Balance' })
    expect(within(balance).getByText('-£20.00')).toBeInTheDocument()
    expect(within(balance).getByText(/Owes money/)).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Sam Smith' })).toHaveAttribute('href', `/students/${sam.id}`)
    expect(await screen.findByText('06/03/2026')).toBeInTheDocument()
    expect(screen.getByText('+£40.00')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Add payment' })).toHaveAttribute('href', `/payments/new?payee_id=${pat.id}`)
    expect(asked).toEqual({ students: pat.id, payments: pat.id })
  })

  it('saves changes to the payee', async () => {
    let body: unknown = null
    server.use(
      http.patch('*/api/v1/payees/:id/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(makePayee({ phone_number: '07700 900123' }))
      }),
    )
    const user = userEvent.setup()
    renderApp(`/payees/${pat.id}`)

    await user.type(await screen.findByLabelText('Phone number (optional)'), '07700 900123')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Saved')
    expect(body).toMatchObject({ phone_number: '07700 900123', email: 'pat@example.com' })
  })

  it('explains a payee that doesn’t exist', async () => {
    renderApp(`/payees/${lee.id}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('doesn’t exist')
  })
})
