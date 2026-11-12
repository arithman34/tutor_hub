import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { api, unwrap } from '../api/client'
import { useMe } from '../auth'
import { formatChange, formatMoney } from '../format'

function StatCard({ label, value, note, tone }: { label: string; value: ReactNode; note?: string | null; tone?: 'good' | 'bad' }) {
  const valueColour = tone === 'good' ? 'text-green-600 dark:text-green-400' : tone === 'bad' ? 'text-red-600 dark:text-red-400' : ''
  return (
    <div className="card p-5">
      <p className="text-xs tracking-wider text-gray-500 uppercase dark:text-gray-400">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${valueColour}`}>{value}</p>
      {note && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{note}</p>}
    </div>
  )
}

export function DashboardPage() {
  const me = useMe()
  // useQuery fetches once, caches the result under the key, and gives the
  // component isPending / error / data to render from.
  const stats = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => unwrap(await api.GET('/api/v1/analytics/dashboard')),
  })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Welcome back{me.data ? `, ${me.data.first_name}` : ''}</h1>

      {stats.isPending && <p className="text-sm text-gray-500 dark:text-gray-400">Loading your numbers…</p>}

      {stats.isError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          Couldn't load the dashboard: {stats.error.message}
        </p>
      )}

      {stats.data && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Revenue this month" value={formatMoney(stats.data.revenue_this_month)} note={formatChange(stats.data.mom_trend) ?? 'No prior month data'} />
          <StatCard label="Revenue this year" value={formatMoney(stats.data.revenue_this_year)} />
          <StatCard label="Revenue all-time" value={formatMoney(stats.data.revenue_alltime)} />
          <StatCard
            label="Outstanding"
            value={formatMoney(stats.data.outstanding_total)}
            tone={stats.data.outstanding_payees ? 'bad' : 'good'}
            note={
              stats.data.outstanding_payees
                ? `${stats.data.outstanding_payees} payee${stats.data.outstanding_payees === 1 ? '' : 's'} owe you`
                : 'Nobody owes you anything'
            }
          />
          <StatCard label="Active students" value={stats.data.active_students} />
          <StatCard label="Sessions this week" value={stats.data.sessions_this_week} />
          <StatCard label="Sessions this month" value={stats.data.sessions_this_month} note={formatChange(stats.data.sessions_pct_change) ?? 'No prior month data'} />
          <StatCard label="Hours taught (month)" value={`${stats.data.hours_this_month.toFixed(1)}h`} note={formatChange(stats.data.hours_pct_change) ?? 'No prior month data'} />
        </div>
      )}
    </div>
  )
}
