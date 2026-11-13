import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '../../test/render'
import { server, testDashboard } from '../../test/server'

describe('dashboard', () => {
  it('shows the headline numbers, compared with the same days last month', async () => {
    renderApp('/')

    const money = await screen.findByRole('region', { name: 'Money' })
    expect(within(money).getByText('£840.00')).toBeInTheDocument()
    expect(within(money).getByText('vs 1–13 Oct', { exact: false })).toBeInTheDocument()
    expect(within(money).getByText('~£1,210')).toBeInTheDocument()
    expect(within(money).getByText('£12,345.50 all-time')).toBeInTheDocument()
    expect(within(money).getByText('£38.40')).toBeInTheDocument()
    expect(within(money).getByText('Nobody owes you anything')).toBeInTheDocument()

    const teaching = screen.getByRole('region', { name: 'Teaching' })
    expect(within(teaching).getByText('21.5h')).toBeInTheDocument()
    expect(within(teaching).getByText('6 taught this month')).toBeInTheDocument()
    expect(within(teaching).getByText('Nothing to compare with previous 7 days')).toBeInTheDocument()
  })

  it('shows rises and falls as words for screen readers, not just colour', async () => {
    renderApp('/')

    const money = await screen.findByRole('region', { name: 'Money' })
    expect(within(money).getByText('Up')).toBeInTheDocument()
    const teaching = screen.getByRole('region', { name: 'Teaching' })
    expect(within(teaching).getByText('Down')).toBeInTheDocument()
    expect(within(teaching).getByText('No change')).toBeInTheDocument()
  })

  it('says who owes money', async () => {
    server.use(http.get('*/api/v1/analytics/dashboard', () => HttpResponse.json({ ...testDashboard, outstanding_total: 80, outstanding_payees: 2 })))
    renderApp('/')
    expect(await screen.findByText('2 payees owe you')).toBeInTheDocument()
  })

  it('links to logging a session', async () => {
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Log session' })).toHaveAttribute('href', '/sessions/new')
  })

  it('charts the last 12 months', async () => {
    renderApp('/')
    expect(await screen.findByRole('img', { name: 'Revenue for each of the last 12 months' })).toHaveAttribute('data-months', '12')
  })

  it('lists upcoming sessions by day', async () => {
    const today = new Date()
    const date = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    server.use(
      http.get('*/api/v1/analytics/dashboard/upcoming', () =>
        HttpResponse.json({
          sessions: [
            {
              id: 's1',
              student_id: 'a1',
              student_name: 'Sam Smith',
              level: 'GCSE',
              topic_tags: 'algebra',
              start: `${date}T16:00:00Z`,
              end: `${date}T17:00:00Z`,
            },
          ],
        }),
      ),
    )
    renderApp('/')

    const todayList = await screen.findByRole('region', { name: 'Today' })
    const link = within(todayList).getByRole('link', { name: /Sam Smith/ })
    expect(link).toHaveAttribute('href', '/sessions/s1')
    expect(link).toHaveTextContent('GCSE · algebra')
    expect(link).toHaveTextContent('16:00')
  })

  it('says when nothing is booked', async () => {
    renderApp('/')
    expect(await screen.findByText('Nothing booked for the next few days.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Schedule a session' })).toHaveAttribute('href', '/sessions/schedule')
  })

  it('breaks this month down by student, with totals', async () => {
    renderApp('/')

    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Sam Smith')
    expect(rows[1]).toHaveTextContent('£160.00')
    expect(rows[1]).toHaveTextContent('54%')
    expect(rows.at(-1)).toHaveTextContent('Total78.5h£295.00')
  })

  it('says when it can’t load', async () => {
    server.use(http.get('*/api/v1/analytics/dashboard', () => HttpResponse.json({ detail: 'Forbidden.' }, { status: 403 })))
    renderApp('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Forbidden.')
  })
})
