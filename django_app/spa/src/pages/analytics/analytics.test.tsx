import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Trends } from '../../api/types'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'
import { bucketLabel, formatValue } from './trendFormat'

// jsdom can't draw on a <canvas>, so stand in for the chart and record what it was given.
const chartProps = vi.hoisted(() => [] as { data: { labels: string[]; datasets: { label: string; type: string; yAxisID: string; data: number[] }[] } }[])
vi.mock('react-chartjs-2', () => ({
  Chart: (props: (typeof chartProps)[number] & { 'aria-label': string }) => {
    chartProps.push(props)
    return <div role="img" aria-label={props['aria-label']} />
  },
}))

function trends(overrides: Partial<Trends> = {}, scale = 1): Trends {
  return {
    range: '12m',
    granularity: 'month',
    start: '2026-01-01T00:00:00Z',
    end: '2026-03-31T23:59:59Z',
    labels: ['2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z', '2026-03-01T00:00:00Z'],
    charts: [
      {
        key: 'sessions',
        title: 'Sessions',
        series: [
          { key: 'sessions_count', label: 'Sessions', unit: 'count', type: 'bar', axis: 'y', data: [2 * scale, 3 * scale, 4 * scale], total: 9 * scale, change: 12.5 },
          { key: 'sessions_hours', label: 'Hours taught', unit: 'hours', type: 'line', axis: 'y1', data: [2 * scale, 3 * scale, 4.5 * scale], total: 9.5 * scale, change: -10 },
        ],
      },
      {
        key: 'payments',
        title: 'Payments',
        series: [
          { key: 'payments_amount', label: 'Received', unit: 'currency', type: 'bar', axis: 'y', data: [100 * scale, 0, 250 * scale], total: 350 * scale, change: null },
        ],
      },
    ],
    ...overrides,
  }
}

function serveTrends(response: (params: URLSearchParams) => Trends = () => trends()) {
  const seen: URLSearchParams[] = []
  server.use(
    http.get('*/api/v1/analytics/trends', ({ request }) => {
      const params = new URL(request.url).searchParams
      seen.push(params)
      return HttpResponse.json(response(params))
    }),
  )
  return seen
}

beforeEach(() => {
  chartProps.length = 0
  server.use(
    http.get('*/api/v1/analytics/filters', () =>
      HttpResponse.json({
        students: [{ id: '22222222-2222-4222-8222-222222222222', name: 'Sam Smith' }],
        payees: [{ id: '11111111-1111-4111-8111-111111111111', name: 'Pat Parent' }],
      }),
    ),
  )
})

describe('analytics page', () => {
  it('shows each chart’s totals and changes, and the period covered', async () => {
    serveTrends()
    renderApp('/analytics')

    const sessions = await screen.findByRole('region', { name: 'Sessions' })
    expect(within(sessions).getByText('9')).toBeInTheDocument()
    expect(within(sessions).getByText('▲ 12.5% vs prior period')).toBeInTheDocument()
    expect(within(sessions).getByText('9.5h')).toBeInTheDocument()
    expect(within(sessions).getByText('▼ 10% vs prior period')).toBeInTheDocument()

    const payments = screen.getByRole('region', { name: 'Payments' })
    expect(within(payments).getByText('£350.00')).toBeInTheDocument()
    expect(within(payments).getByText('No prior data')).toBeInTheDocument()

    expect(screen.getByText('01 Jan 2026 – 31 Mar 2026')).toBeInTheDocument()
  })

  it('hands each chart its labels, bars and lines, and axes', async () => {
    serveTrends()
    renderApp('/analytics')
    await screen.findByRole('img', { name: 'Sessions chart' })

    const sessions = chartProps.findLast((props) => props.data.datasets[0]?.label === 'Sessions')!
    expect(sessions.data.labels).toEqual(['Jan 26', 'Feb 26', 'Mar 26'])
    expect(sessions.data.datasets.map(({ type, yAxisID, data }) => ({ type, yAxisID, data }))).toEqual([
      { type: 'bar', yAxisID: 'y', data: [2, 3, 4] },
      { type: 'line', yAxisID: 'y1', data: [2, 3, 4.5] },
    ])
  })

  it('switches period presets and clears custom dates', async () => {
    const seen = serveTrends()
    const user = userEvent.setup()
    renderApp('/analytics?start=2026-01-01&end=2026-02-01')

    await screen.findByRole('region', { name: 'Sessions' })
    expect(seen.at(-1)?.get('start')).toBe('2026-01-01')
    // With custom dates, no preset is selected.
    expect(screen.getByRole('button', { name: '12M' })).toHaveAttribute('aria-pressed', 'false')

    await user.click(screen.getByRole('button', { name: '3M' }))

    await waitFor(() => expect(seen.at(-1)?.get('range')).toBe('3m'))
    expect(seen.at(-1)?.has('start')).toBe(false)
    expect(screen.getByRole('button', { name: '3M' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('From')).toHaveValue('')
  })

  it('says when a long range is grouped more coarsely than asked', async () => {
    const seen = serveTrends((params) => trends({ granularity: params.get('granularity') === 'day' ? 'week' : 'month' }))
    const user = userEvent.setup()
    renderApp('/analytics')

    await user.selectOptions(await screen.findByLabelText('Group by'), 'day')

    expect(await screen.findByRole('status')).toHaveTextContent('too long to group by day, so it\'s grouped by week instead')
    expect(seen.at(-1)?.get('granularity')).toBe('day')
  })

  it('filters by student and explains how payments are matched', async () => {
    const seen = serveTrends()
    const user = userEvent.setup()
    renderApp('/analytics')

    // The student list loads separately; wait for it.
    await screen.findByRole('option', { name: 'Sam Smith' })
    await user.selectOptions(screen.getByLabelText('Student'), 'Sam Smith')

    await waitFor(() => expect(seen.at(-1)?.get('student_id')).toBe('22222222-2222-4222-8222-222222222222'))
    const payments = screen.getByRole('region', { name: 'Payments' })
    expect(within(payments).getByText(/Payments are recorded per payee/)).toBeInTheDocument()
  })

  it('resets every filter', async () => {
    const seen = serveTrends()
    const user = userEvent.setup()
    renderApp('/analytics?range=3m&granularity=week&payee_id=11111111-1111-4111-8111-111111111111')

    await screen.findByRole('option', { name: 'Pat Parent' })
    expect(screen.getByLabelText('Payee')).toHaveValue('11111111-1111-4111-8111-111111111111')
    await user.click(screen.getByRole('button', { name: 'Reset' }))

    await waitFor(() => expect(seen.at(-1)?.toString()).toBe('range=12m&granularity=month'))
    expect(screen.getByLabelText('Payee')).toHaveValue('')
  })

  it('says when there is nothing in the period', async () => {
    serveTrends(() => trends({}, 0))
    renderApp('/analytics')
    expect(await screen.findByText('No data in this period.')).toBeInTheDocument()
  })

  it('reports a failure to load', async () => {
    server.use(http.get('*/api/v1/analytics/trends', () => HttpResponse.json({ detail: 'Nope.' }, { status: 403 })))
    renderApp('/analytics')
    expect(await screen.findByRole('alert')).toHaveTextContent('Nope.')
  })
})

describe('chart formatting', () => {
  it('formats values by unit', () => {
    expect(formatValue(1234.5, 'currency')).toBe('£1,234.50')
    expect(formatValue(3, 'hours')).toBe('3.0h')
    expect(formatValue(7, 'count')).toBe('7')
    expect(formatValue(2.25, 'count')).toBe('2.3')
  })

  it('labels buckets in UTC, so a month never slips into the previous one', () => {
    expect(bucketLabel('2026-03-01T00:00:00Z', 'month')).toBe('Mar 26')
    expect(bucketLabel('2026-03-09T00:00:00Z', 'week')).toBe('09 Mar')
  })
})
