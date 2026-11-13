import { CheckCircle2, CircleAlert, Plus } from 'lucide-react'
import { lazy, Suspense, useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { Dashboard } from '../../api/types'
import { useMe } from '../../auth'
import { buttonPrimary, ErrorMessage, Loading } from '../../components/ui'
import { formatDayRange, formatLongDate, formatMoney, formatMoneyRounded } from '../../format'
import { useDashboardStats, useRevenueByMonth, useStudentBreakdown, useUpcomingSessions } from './queries'
import { Sparkline } from './Sparkline'
import { Delta, labelClass, noteClass, StatCard } from './StatCard'
import { StudentBreakdown } from './StudentBreakdown'
import { UpcomingSessions } from './UpcomingSessions'

// Chart.js is big, so the chart loads after the numbers rather than with the
// first page (the dashboard is in the main bundle; see App.tsx).
const RevenueChart = lazy(() => import('./RevenueChart').then((module) => ({ default: module.RevenueChart })))

/**
 * Cards sit in auto-fitting columns at least 200px wide. The hero card only
 * spans two once the row has room for five columns (1064px), so on a 1280px
 * laptop the four money cards still fit on one row.
 */
const cardGrid = 'grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]'

function Panel({ title, note, action, children, className = '' }: { title: string; note?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  const id = `panel-${title.toLowerCase().replace(/\W+/g, '-')}`
  return (
    <section aria-labelledby={id} className={`card flex flex-col p-5 ${className}`}>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 id={id} className="font-semibold">
          {title}
        </h2>
        {note && <p className={noteClass}>{note}</p>}
        {action && <div className="ml-auto">{action}</div>}
      </div>
      {children}
    </section>
  )
}

function PanelStatus({ query, children }: { query: { isPending: boolean; isError: boolean; error: Error | null }; children: ReactNode }) {
  if (query.isPending) return <Loading />
  if (query.isError) return <ErrorMessage>Couldn't load this: {query.error?.message}</ErrorMessage>
  return <>{children}</>
}

function HeroCard({ stats, period }: { stats: Dashboard; period: string }) {
  return (
    <div className="card relative overflow-hidden px-4 py-3 @min-[1064px]:col-span-2">
      <Sparkline values={stats.revenue_month_to_date} className="pointer-events-none absolute right-0 bottom-0 h-14 w-3/5" />
      <div className="relative">
        <p className={labelClass}>Revenue this month</p>
        <p className="mt-1 text-3xl leading-9 font-semibold tracking-tight tabular-nums">{formatMoney(stats.revenue_this_month)}</p>
        <div className="mt-1 flex flex-col gap-0.5">
          <Delta percent={stats.mom_trend} period={period} />
          <span className={noteClass}>
            {stats.revenue_projected !== null ? (
              <>
                On track for <span className="font-medium text-slate-700 tabular-nums dark:text-slate-200">~{formatMoneyRounded(stats.revenue_projected)}</span>
              </>
            ) : (
              'No projection until there’s a full month to go on'
            )}
          </span>
        </div>
      </div>
    </div>
  )
}

function StatCards({ stats }: { stats: Dashboard }) {
  const period = formatDayRange(stats.compare_from, stats.compare_to)
  const owing = stats.outstanding_payees

  return (
    <div className="space-y-4">
      <section aria-label="Money" className={cardGrid}>
        <HeroCard stats={stats} period={period} />
        <StatCard
          label="Revenue this year"
          value={formatMoney(stats.revenue_this_year)}
          note={<span className={noteClass}>{formatMoney(stats.revenue_alltime)} all-time</span>}
        />
        <StatCard
          label="Average £/hour"
          value={stats.average_hourly_rate === null ? '–' : formatMoney(stats.average_hourly_rate)}
          note={<span className={noteClass}>Over {stats.hours_this_year.toFixed(1)}h taught this year</span>}
        />
        <StatCard
          label="Outstanding"
          value={formatMoney(stats.outstanding_total)}
          note={
            owing ? (
              <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-[#f59e0b]">
                <CircleAlert aria-hidden="true" className="h-3.5 w-3.5" />
                {owing} payee{owing === 1 ? '' : 's'} owe{owing === 1 ? 's' : ''} you
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-[#22c55e]">
                <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
                Nobody owes you anything
              </span>
            )
          }
        />
      </section>

      <section aria-label="Teaching" className={cardGrid}>
        <StatCard
          label="Active students"
          value={stats.active_students}
          note={<span className={noteClass}>{stats.students_taught_this_month} taught this month</span>}
        />
        <StatCard label="Sessions this week" value={stats.sessions_this_week} note={<Delta percent={stats.sessions_week_pct_change} period="previous 7 days" />} />
        <StatCard label="Sessions this month" value={stats.sessions_this_month} note={<Delta percent={stats.sessions_pct_change} period={period} />} />
        <StatCard label="Hours taught (month)" value={`${stats.hours_this_month.toFixed(1)}h`} note={<Delta percent={stats.hours_pct_change} period={period} />} />
      </section>
    </div>
  )
}

export function DashboardPage() {
  const me = useMe()
  // Read once, so "Today" and the date in the header agree for the whole visit.
  const [today] = useState(() => new Date())
  const stats = useDashboardStats()
  const revenue = useRevenueByMonth()
  const upcoming = useUpcomingSessions()
  const students = useStudentBreakdown()

  return (
    <div className="@container space-y-6">
      <header className="flex flex-wrap items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold">Welcome back{me.data ? `, ${me.data.first_name}` : ''}</h1>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{formatLongDate(today)}</p>
        </div>
        <Link to="/sessions/new" className={`${buttonPrimary} ml-auto inline-flex items-center gap-1.5`}>
          <Plus aria-hidden="true" className="h-4 w-4" strokeWidth={2.5} />
          Log session
        </Link>
      </header>

      {stats.isPending && <Loading>Loading your numbers…</Loading>}
      {stats.isError && <ErrorMessage>Couldn't load the dashboard: {stats.error.message}</ErrorMessage>}
      {stats.data && <StatCards stats={stats.data} />}

      <div className="grid gap-4 @min-[900px]:grid-cols-3">
        <Panel title="Revenue" note="Payments received, last 12 months" className="@min-[900px]:col-span-2">
          <PanelStatus query={revenue}>
            <div className="h-64">
              <Suspense fallback={<Loading>Loading chart…</Loading>}>
                {revenue.data && <RevenueChart months={revenue.data} projected={stats.data?.revenue_projected ?? null} />}
              </Suspense>
            </div>
            <div className={`mt-3 flex flex-wrap gap-4 ${noteClass}`} aria-hidden="true">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm bg-blue-500" /> Received
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-sm border border-blue-500 bg-[repeating-linear-gradient(135deg,#3b82f6_0_2px,transparent_2px_4px)]" /> This month so far
              </span>
              {/* Only when the chart draws the faint projected bar, i.e. more is expected. */}
              {stats.data?.revenue_projected != null && stats.data.revenue_projected > stats.data.revenue_this_month && (
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm border border-slate-400/60 bg-slate-400/15" /> On track for
                </span>
              )}
            </div>
          </PanelStatus>
        </Panel>

        <Panel
          title="Upcoming sessions"
          action={
            <Link to="/sessions" className="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400">
              All sessions
            </Link>
          }
        >
          <PanelStatus query={upcoming}>{upcoming.data && <UpcomingSessions sessions={upcoming.data} today={today} />}</PanelStatus>
        </Panel>
      </div>

      <Panel title="Students this month" note="Hours taught and billed at each student’s hourly rate">
        <PanelStatus query={students}>{students.data && <StudentBreakdown rows={students.data} />}</PanelStatus>
      </Panel>
    </div>
  )
}
