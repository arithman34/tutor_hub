import { useState, type FormEvent } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { CalendarSessionItem } from '../../api/types'
import { Tabs } from '../../components/Tabs'
import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { SearchForm } from '../../components/SearchForm'
import { formatDate } from '../../format'
import { useIsDemo } from '../../auth'
import { useConnectGoogle } from '../connections/queries'
import { useCalendarSessions, useZoomSweep, type SessionPeriod, type SessionStatus } from './queries'
import { ZoomCatchUpButton, ZoomSweepResult } from './ZoomCatchUp'
import { isManualLog, zoomOutcomeLabel } from './zoomOutcome'

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
  const sweep = useZoomSweep()
  const isDemo = useIsDemo()

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
      <PageHeader title="Sessions" description="Lessons from your Tutoring calendar, and the notes you’ve logged for them.">
        <ZoomCatchUpButton sweep={sweep} />
        <Link to="/sessions/schedule" className={buttonPrimary}>
          Schedule session
        </Link>
      </PageHeader>

      <ZoomSweepResult sweep={sweep} />

      {notice && (
        <p role="status" className="alert alert-success mb-4">
          {notice}
        </p>
      )}

      <SearchForm
        id="session-search"
        label="Search sessions"
        placeholder="Search sessions…"
        value={draft}
        onChange={setDraft}
        onSubmit={handleSearch}
        onClear={q ? () => {
              setDraft('')
              update({ q: '' })
            } : undefined}
        className="mb-4"
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Tabs label="Logged status" options={STATUS_OPTIONS} value={status} onChange={(value) => update({ status: value })} />
        <Tabs label="Period" options={PERIOD_OPTIONS} value={period} onChange={(value) => update({ period: value })} />
      </div>

      {sessions.isPending && <Loading>Loading your calendar…</Loading>}

      {notConnected && isDemo && (
        <p className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-white/5 dark:bg-slate-800 dark:text-slate-300">
          This list comes from the tutor's Google Calendar, which the demo isn't linked to. Open a student from the{' '}
          <Link to="/students" className="font-medium underline">
            Students
          </Link>{' '}
          page to see their logged lessons.
        </p>
      )}
      {notConnected && !isDemo && (
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
            <p className="mb-3 text-sm muted">
              {items.length} result{items.length === 1 ? '' : 's'} for “{q}”
            </p>
          )}
          <div className="card overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Status</th>
                  <th>
                    <span className="sr-only">Action</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => (
                  <tr key={item.event_id}>
                    <td className="font-medium text-slate-900 dark:text-white">{item.summary || '(No title)'}</td>
                    <td>{formatDate(item.date)}</td>
                    <td>
                      {item.start_time ? `${item.start_time}${item.end_time ? ` – ${item.end_time}` : ''}` : <span className="text-slate-400">All day</span>}
                    </td>
                    <td>
                      {item.logged ? (
                        <span className="inline-flex flex-wrap items-center gap-1.5">
                          <span className="badge badge-green">Logged</span>
                          {isManualLog(item.zoom_outcome) && (
                            <span
                              title="Logged manually"
                              className="badge badge-slate"
                            >
                              Manual
                            </span>
                          )}
                          {item.zoom_outcome !== null && (
                            <span
                              title={zoomOutcomeLabel(item.zoom_outcome)}
                              className="badge badge-blue"
                            >
                              Zoom<span className="sr-only">: {zoomOutcomeLabel(item.zoom_outcome)}</span>
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="badge badge-amber">Not logged</span>
                      )}
                    </td>
                    <td className="text-right">
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
                    <td colSpan={5} className="empty">
                      {emptyMessage(status, period)}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {items.length > 0 && (
            <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm muted">
                Showing {(currentPage - 1) * PAGE_SIZE + 1}–{(currentPage - 1) * PAGE_SIZE + pageItems.length} of {items.length}
              </p>
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <button type="button" disabled={currentPage <= 1} onClick={() => update({ page: String(currentPage - 1) })} className={buttonSecondary}>
                    Previous
                  </button>
                  <span className="px-2 text-sm muted">
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
