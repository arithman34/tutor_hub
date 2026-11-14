import { Link } from 'react-router'

import { useIsDemo } from '../../auth'
import { buttonSecondary } from '../../components/ui'
import { formatDate, wallTime } from '../../format'
import { useZoomStatus } from '../connections/queries'
import type { useZoomSweep } from './queries'
import { zoomOutcomeShort } from './zoomOutcome'

type Sweep = ReturnType<typeof useZoomSweep>
type SweepResult = NonNullable<Sweep['data']>

function plural(count: number, word: string) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

function describeSweep(result: SweepResult) {
  const parts = []
  if (result.logged) parts.push(`logged ${plural(result.logged, 'lesson')}`)
  if (result.no_shows) parts.push(`logged ${plural(result.no_shows, 'no-show')}`)
  if (result.notes_filled) parts.push(`filled notes on ${plural(result.notes_filled, 'session')}`)
  if (result.linked) parts.push(`matched ${plural(result.linked, 'session')} you'd already written notes for`)
  if (result.waiting) parts.push(`${plural(result.waiting, 'lesson')} still waiting for Zoom`)
  if (result.failed) parts.push(`${plural(result.failed, 'lesson')} couldn't be logged`)
  return parts.length ? `Zoom: ${parts.join(', ')}.` : 'Zoom: nothing new to log.'
}

/**
 * Lessons are logged automatically when Zoom says a summary is ready. This is
 * the manual catch-up, for anything missed (or a no-show Zoom never summarised).
 */
export function ZoomCatchUpButton({ sweep }: { sweep: Sweep }) {
  const isDemo = useIsDemo()
  const zoom = useZoomStatus({ enabled: !isDemo })
  if (isDemo || !zoom.data?.connected) return null

  return (
    <button type="button" onClick={() => sweep.mutate()} disabled={sweep.isPending} className={buttonSecondary}>
      {sweep.isPending ? 'Checking Zoom…' : 'Check Zoom for missed lessons'}
    </button>
  )
}

/** What the last catch-up did, with a link to every session it logged or changed. */
export function ZoomSweepResult({ sweep }: { sweep: Sweep }) {
  if (sweep.isError) {
    return (
      <p role="alert" className="alert alert-error mb-4">
        {sweep.error.message}
      </p>
    )
  }
  if (!sweep.data) return null

  return (
    <div role="status" className="alert alert-blue mb-4">
      <p>{describeSweep(sweep.data)}</p>
      {sweep.data.sessions.length > 0 && (
        <ul className="mt-2 space-y-1">
          {sweep.data.sessions.map((item) => (
            <li key={item.session_id}>
              <Link to={`/sessions/${item.session_id}`} className="text-blue-700 hover:underline dark:text-blue-300">
                {item.student_name}, {formatDate(item.start)} {wallTime(item.start)}
              </Link>
              <span className="text-slate-600 dark:text-slate-400"> · {zoomOutcomeShort(item.outcome)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
