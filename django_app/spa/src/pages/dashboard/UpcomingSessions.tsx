import { CalendarPlus } from 'lucide-react'
import { Link } from 'react-router'

import type { UpcomingSession } from '../../api/types'
import { localDate, wallDate, wallTime } from '../../format'
import { labelClass, noteClass } from './StatCard'

const dayName = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })

/** "Today", "Tomorrow" or "Mon 16 Nov" for a "2026-11-16" date. */
function dayHeading(date: string, today: Date): string {
  if (date === localDate(today)) return 'Today'
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  if (date === localDate(tomorrow)) return 'Tomorrow'
  return dayName.format(new Date(`${date}T00:00:00Z`))
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

/** Lessons booked for today and the next few days, grouped by day. */
export function UpcomingSessions({ sessions, today }: { sessions: UpcomingSession[]; today: Date }) {
  if (sessions.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 py-8 text-center">
        <CalendarPlus aria-hidden="true" className="h-8 w-8 text-slate-400" strokeWidth={1.5} />
        <p className={noteClass}>Nothing booked for the next few days.</p>
        <Link to="/sessions/schedule" className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400">
          Schedule a session
        </Link>
      </div>
    )
  }

  const days = new Map<string, UpcomingSession[]>()
  for (const session of sessions) {
    const date = wallDate(session.start)
    days.set(date, [...(days.get(date) ?? []), session])
  }

  return (
    <div className="space-y-4">
      {[...days].map(([date, daySessions]) => (
        <section key={date} aria-label={dayHeading(date, today)}>
          <h3 className={`${labelClass} mb-1.5`}>{dayHeading(date, today)}</h3>
          <ul className="space-y-1">
            {daySessions.map((session) => {
              const subject = [session.level, session.topic_tags].filter(Boolean).join(' · ')
              return (
                <li key={session.id}>
                  <Link
                    to={`/sessions/${session.id}`}
                    className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700/50"
                  >
                    <span
                      aria-hidden="true"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
                    >
                      {initials(session.student_name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{session.student_name}</span>
                      <span className={`block truncate ${noteClass}`}>{subject || 'No subject set'}</span>
                    </span>
                    <span className="shrink-0 text-right text-sm tabular-nums">
                      {wallTime(session.start)}
                      <span className={`block ${noteClass}`}>to {wallTime(session.end)}</span>
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
