import { useState, type FormEvent } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { CalendarSessionItem } from '../../api/types'
import { Tabs } from '../../components/Tabs'
import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { formatDate } from '../../format'
import { useConnectGoogle } from '../connections/queries'
import { useCalendarSessions, type SessionPeriod, type SessionStatus } from './queries'

const PAGE_SIZE = 50

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'logged', label: 'Logged' },
  { value: 'unlogged', label: 'Not logged' },
] as const satisfies readonly { value: SessionStatus; label: string }[]

const PERIOD_OPTIONS = [
  { value: 'all', label: 'All time' },
  { value: 'past', label: 'Past' },
  { value: 'today', label: 'Today' },
  { value: 'future', label: 'Future' },
] as const satisfies readonly { value: SessionPeriod; label: string }[]

function oneOf<T extends string>(value: string | null, options: readonly { value: T }[], fallback: T): T {
  return options.find((option) => option.value === value)?.value ?? fallback
}

function emptyMessage(status: SessionStatus, period: SessionPeriod): string {
  if (status === 'unlogged') return "No unlogged sessions. You're all caught up."
  if (period === 'today') return 'No sessions today.'
  if (period === 'future') return 'No upcoming sessions.'
  if (period === 'past') return 'No past sessions found.'
  return 'No sessions found in your calendar.'
}

/** The log-session form, pre-filled from a calendar event. */
function logLink(item: CalendarSessionItem): string {
  const params = new URLSearchParams({
    date: item.date,
    start_time: item.start_time,
    end_time: item.end_time,
    event_id: item.event_id,
    html_link: item.html_link,
  })
  if (item.student_id) params.set('student_id', item.student_id)
  return `/sessions/new?${params}`
}

export function SessionsPage() {
  // Filters, search and page all live in the URL, so a reload or the back
  // button keeps them.
  const [searchParams, setSearchParams] = useSearchParams()
  const status = oneOf(searchParams.get('status'), STATUS_OPTIONS, 'all')
  const period = oneOf(searchParams.get('period'), PERIOD_OPTIONS, 'all')
  const q = searchParams.get('q') ?? ''
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const [draft, setDraft] = useState(q)
  // Set by the schedule page after a booking. Any filter change drops it.
  const notice = (useLocation().state as { notice?: string } | null)?.notice
  const sessions = useCalendarSessions(status, period, q)
  const reconnect = useConnectGoogle()

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value && value !== 'all') next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next)
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    update({ q: draft.trim() })
  }

  const notConnected = sessions.error instanceof ApiError && sessions.error.status === 409
  const items = sessions.data?.items ?? []
  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const pageItems = items.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  return (
    <div>
      <PageHeader title="Sessions">
        <Link to="/sessions/schedule" className={buttonPrimary}>
          Schedule session
        </Link>
      </PageHeader>

      {notice && (
        <p role="status" className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
          {notice}
        </p>
      )}

      <form role="search" onSubmit={handleSearch} className="mb-4 flex flex-wrap gap-2">
        <label htmlFor="session-search" className="sr-only">
          Search sessions
        </label>
        <input
          id="session-search"
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Search sessions…"
          className="input sm:!w-64"
        />
        <button type="submit" className={buttonPrimary}>
          Search
        </button>
        {q && (
          <button
            type="button"
            onClick={() => {
              setDraft('')
              update({ q: '' })
            }}
            className={buttonSecondary}
          >
            Clear
          </button>
        )}
      </form>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Tabs label="Logged status" options={STATUS_OPTIONS} value={status} onChange={(value) => update({ status: value })} />
        <Tabs label="Period" options={PERIOD_OPTIONS} value={period} onChange={(value) => update({ period: value })} />
      </div>

      {sessions.isPending && <Loading>Loading your calendar…</Loading>}

      {notConnected && (
        <ErrorMessage>
          Connect Google Calendar to see your sessions here.{' '}
          <Link to="/connections" className="font-medium underline">
            Go to Connections
          </Link>
        </ErrorMessage>
      )}
      {sessions.isError && !notConnected && <ErrorMessage>Couldn't load sessions: {sessions.error.message}</ErrorMessage>}

      {sessions.data?.error && (
        <div className="mb-4">
          <ErrorMessage>
            {sessions.data.error}{' '}
            {sessions.data.error.includes('reconnect') && (
              // Straight to Google: when Google has only refused the calendar, the
              // connection still counts as connected, so Connections would offer
              // just "Disconnect".
              <button type="button" onClick={() => reconnect.mutate()} disabled={reconnect.isPending || reconnect.isSuccess} className="font-medium underline">
                Reconnect Google Calendar
              </button>
            )}
          </ErrorMessage>
        </div>
      )}

      {sessions.data && (
        <>
          {q && (
            <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">
              {items.length} result{items.length === 1 ? '' : 's'} for “{q}”
            </p>
          )}
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th className="px-6 py-3">Session</th>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Time</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => (
                  <tr key={item.event_id} className="border-b border-gray-200 last:border-0 dark:border-gray-700">
                    <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">{item.summary || '(No title)'}</td>
                    <td className="px-6 py-4">{formatDate(item.date)}</td>
                    <td className="px-6 py-4">
                      {item.start_time ? `${item.start_time}${item.end_time ? ` – ${item.end_time}` : ''}` : <span className="text-gray-400">All day</span>}
                    </td>
                    <td className="px-6 py-4">
                      {item.logged ? (
                        <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/50 dark:text-green-300">Logged</span>
                      ) : (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">Not logged</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {item.logged && item.session_id ? (
                        <Link to={`/sessions/${item.session_id}`} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                          View
                        </Link>
                      ) : (
                        <Link to={logLink(item)} className={`${buttonPrimary} px-3 py-1.5 text-xs`}>
                          Log session
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-gray-400">
                      {emptyMessage(status, period)}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {items.length > 0 && (
            <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Showing {(currentPage - 1) * PAGE_SIZE + 1}–{(currentPage - 1) * PAGE_SIZE + pageItems.length} of {items.length}
              </p>
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <button type="button" disabled={currentPage <= 1} onClick={() => update({ page: String(currentPage - 1) })} className={buttonSecondary}>
                    Previous
                  </button>
                  <span className="px-2 text-sm text-gray-500 dark:text-gray-400">
                    Page {currentPage} of {totalPages}
                  </span>
                  <button type="button" disabled={currentPage >= totalPages} onClick={() => update({ page: String(currentPage + 1) })} className={buttonSecondary}>
                    Next
                  </button>
                </div>
              )}
            </nav>
          )}
        </>
      )}
    </div>
  )
}
