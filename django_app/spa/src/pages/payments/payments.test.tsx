import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Payee, Payment } from '../../api/types'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'

const pat = {
  id: '11111111-1111-4111-8111-111111111111',
  first_name: 'Pat',
  last_name: 'Parent',
  balance: -20,
  student_count: 1,
} as Payee

function payment(index: number): Payment {
  return {
    id: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
    payee: pat.id,
    payee_name: 'Pat Parent',
    amount: `${index}.50`,
    payment_date: '2026-03-06T00:00:00Z',
    payment_reference: null,
    created_at: '2026-03-06T00:00:00Z',
    updated_at: '2026-03-06T00:00:00Z',
  }
}

beforeEach(() => {
  server.use(http.get('*/api/v1/payees/', () => HttpResponse.json([pat])))
})

describe('payments list', () => {
  it('pages through payments on the server, 20 at a time', async () => {
    const asked: URLSearchParams[] = []
    server.use(
      http.get('*/api/v1/payments/', ({ request }) => {
        const params = new URL(request.url).searchParams
        asked.push(params)
        const offset = Number(params.get('offset'))
        const results = Array.from({ length: offset === 0 ? 20 : 5 }, (_, index) => payment(offset + index + 1))
        return HttpResponse.json({ count: 25, next: null, previous: null, results })
      }),
    )
    const user = userEvent.setup()
    renderApp('/payments')

    expect(await screen.findByText('Showing 1–20 of 25')).toBeInTheDocument()
    expect(screen.getByText('+£1.50')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Pat Parent' })[0]).toHaveAttribute('href', `/payees/${pat.id}`)

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('Showing 21–25 of 25')).toBeInTheDocument()
    expect(screen.getByText('+£21.50')).toBeInTheDocument()
    expect(asked.at(-1)?.get('offset')).toBe('20')
    expect(asked.at(-1)?.get('limit')).toBe('20')
  })

  it('searches by payee name', async () => {
    let searched: string | null = null
    server.use(
      http.get('*/api/v1/payments/', ({ request }) => {
        searched = new URL(request.url).searchParams.get('q')
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] })
      }),
    )
    const user = userEvent.setup()
    renderApp('/payments')

    await user.type(await screen.findByLabelText('Search payments'), 'pat')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('No payments match that search')).toBeInTheDocument()
    expect(searched).toBe('pat')
  })
})

describe('adding a payment', () => {
  it('records the payment at the chosen date and returns to the payee', async () => {
    let body: unknown = null
    server.use(
      http.post('*/api/v1/payments/', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ ...payment(40), amount: '40.00' }, { status: 201 })
      }),
      http.get('*/api/v1/payees/:id/', () => HttpResponse.json({ ...pat, email: null, phone_number: null, bank_reference_pattern: null })),
      http.get('*/api/v1/students/', () => HttpResponse.json([])),
      http.get('*/api/v1/payments/', () => HttpResponse.json({ count: 0, next: null, previous: null, results: [] })),
    )
    const user = userEvent.setup()
    renderApp(`/payments/new?payee_id=${pat.id}`)

    expect(await screen.findByLabelText('Payee')).toHaveValue(pat.id)
    await user.type(screen.getByLabelText('Amount (£)'), '40')
    const date = screen.getByLabelText('Payment date')
    await user.clear(date)
    await user.type(date, '2026-03-06')
    await user.type(screen.getByLabelText('Reference (optional)'), 'FT123')
    await user.click(screen.getByRole('button', { name: 'Add payment' }))

    expect(await screen.findByRole('region', { name: 'Balance' })).toBeInTheDocument()
    expect(body).toEqual({ payee: pat.id, amount: '40', payment_date: '2026-03-06T00:00:00Z', payment_reference: 'FT123' })
  })

  it('rejects zero, negative and malformed amounts', async () => {
    let posted = false
    server.use(http.post('*/api/v1/payments/', () => ((posted = true), HttpResponse.json(payment(1), { status: 201 }))))
    const user = userEvent.setup()
    renderApp('/payments/new')

    await user.selectOptions(await screen.findByLabelText('Payee'), 'Pat Parent')
    for (const bad of ['0', '-5', '12.345', 'ten']) {
      await user.clear(screen.getByLabelText('Amount (£)'))
      await user.type(screen.getByLabelText('Amount (£)'), bad)
      await user.click(screen.getByRole('button', { name: 'Add payment' }))
      expect(await screen.findByText('Enter an amount like 40 or 37.50')).toBeInTheDocument()
    }
    await waitFor(() => expect(posted).toBe(false))
  })

  it('asks for a payee first when there are none', async () => {
    server.use(http.get('*/api/v1/payees/', () => HttpResponse.json([])))
    renderApp('/payments/new')
    expect(await screen.findByRole('link', { name: 'Add a payee' })).toHaveAttribute('href', '/payees/new')
  })
})
