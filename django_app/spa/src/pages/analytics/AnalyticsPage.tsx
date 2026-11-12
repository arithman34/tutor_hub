import { useSearchParams } from 'react-router'

import { Field } from '../../components/form'
import { Tabs } from '../../components/Tabs'
import { ErrorMessage, Loading, PageHeader } from '../../components/ui'
import { DEFAULT_FILTERS, GRANULARITIES, RANGES, useFilterOptions, useTrends, type Granularity, type Range, type TrendFilters } from './queries'
import { TrendChartCard } from './TrendChartCard'

const ukDay = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })

function pick<T extends string>(value: string | null, options: readonly T[], fallback: T): T {
  return options.includes(value as T) ? (value as T) : fallback
}

/** The filters, read from the URL so a view can be bookmarked or reloaded. */
function filtersFrom(params: URLSearchParams): TrendFilters {
  return {
    range: pick(params.get('range'), RANGES.map((range) => range.value), DEFAULT_FILTERS.range),
    granularity: pick(params.get('granularity'), GRANULARITIES, DEFAULT_FILTERS.granularity),
    start: params.get('start') ?? '',
    end: params.get('end') ?? '',
    student_id: params.get('student_id') ?? '',
    payee_id: params.get('payee_id') ?? '',
  }
}

export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = filtersFrom(searchParams)
  const trends = useTrends(filters)
  const options = useFilterOptions()
  const customDates = Boolean(filters.start || filters.end)

  function update(changes: Partial<TrendFilters>) {
    const next = { ...filters, ...changes }
    // Only store what differs from the defaults, so the URL stays short.
    const entries = Object.entries(next).filter(([key, value]) => value !== '' && value !== DEFAULT_FILTERS[key as keyof TrendFilters])
    setSearchParams(Object.fromEntries(entries), { replace: true })
  }

  const data = trends.data
  const empty = data?.charts.every((chart) => chart.series.every((series) => series.data.every((value) => value === 0)))
  const coarsened = data && data.granularity !== filters.granularity

  return (
    <div>
      <PageHeader title="Analytics">
        {data && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {ukDay.format(new Date(data.start))} – {ukDay.format(new Date(data.end))}
          </p>
        )}
      </PageHeader>

      <div className="card mb-5 p-5">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Period</span>
            {/* A preset and explicit dates are mutually exclusive; picking a preset clears the dates. */}
            <Tabs
              label="Period"
              options={RANGES}
              value={customDates ? ('' as Range) : filters.range}
              onChange={(range) => update({ range, start: '', end: '' })}
            />
          </div>
          <div className="w-32">
            <Field id="granularity" label="Group by">
              <select id="granularity" value={filters.granularity} onChange={(event) => update({ granularity: event.target.value as Granularity })} className="input">
                {GRANULARITIES.map((granularity) => (
                  <option key={granularity} value={granularity}>
                    {granularity[0]!.toUpperCase() + granularity.slice(1)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="w-40">
            <Field id="start" label="From">
              <input id="start" type="date" value={filters.start} onChange={(event) => update({ start: event.target.value })} className="input" />
            </Field>
          </div>
          <div className="w-40">
            <Field id="end" label="To">
              <input id="end" type="date" value={filters.end} onChange={(event) => update({ end: event.target.value })} className="input" />
            </Field>
          </div>
          <div className="w-44">
            <Field id="student_id" label="Student">
              <select id="student_id" value={filters.student_id} onChange={(event) => update({ student_id: event.target.value })} className="input">
                <option value="">All students</option>
                {options.data?.students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="w-44">
            <Field id="payee_id" label="Payee">
              <select id="payee_id" value={filters.payee_id} onChange={(event) => update({ payee_id: event.target.value })} className="input">
                <option value="">All payees</option>
                {options.data?.payees.map((payee) => (
                  <option key={payee.id} value={payee.id}>
                    {payee.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <button
            type="button"
            onClick={() => setSearchParams({}, { replace: true })}
            className="px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 dark:text-gray-300 dark:hover:text-blue-400"
          >
            Reset
          </button>
        </div>
        {coarsened && (
          <p role="status" className="mt-3 text-xs text-amber-600 dark:text-amber-400">
            That range is too long to group by {filters.granularity}, so it's grouped by {data.granularity} instead.
          </p>
        )}
      </div>

      {trends.isPending && <Loading>Loading your numbers…</Loading>}
      {trends.isError && <ErrorMessage>Couldn't load analytics: {trends.error.message}</ErrorMessage>}

      {data && (
        <div className={`space-y-5 transition-opacity ${trends.isPlaceholderData ? 'opacity-60' : ''}`} aria-busy={trends.isFetching}>
          {empty && <p className="card p-8 text-center text-sm text-gray-400">No data in this period.</p>}
          {data.charts.map((chart) => (
            <TrendChartCard
              key={chart.key}
              chart={chart}
              labels={data.labels}
              granularity={data.granularity}
              note={
                // Payments belong to a payee, not a student, so a student filter matches all their payee's payments.
                chart.key === 'payments' && filters.student_id
                  ? "Payments are recorded per payee, so this matches every payment from the student's payees. A payee shared with another student is counted here too."
                  : null
              }
            />
          ))}
        </div>
      )}
    </div>
  )
}
