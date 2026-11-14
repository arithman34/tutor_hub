import { Link } from 'react-router'

import type { StudentBreakdownRow } from '../../api/types'
import { formatMoney } from '../../format'
import { noteClass } from '../../components/stats'

const headClass = 'px-3 py-2 text-xs font-medium tracking-[0.04em] text-slate-500 uppercase dark:text-slate-400'

/** Each student taught this month, with their share of the month's billed revenue. */
export function StudentBreakdown({ rows }: { rows: StudentBreakdownRow[] }) {
  if (rows.length === 0) {
    return <p className={`py-6 text-center ${noteClass}`}>No sessions taught this month yet.</p>
  }

  const totalRevenue = rows.reduce((sum, row) => sum + row.revenue, 0)
  const totalHours = rows.reduce((sum, row) => sum + row.hours, 0)
  const totalSessions = rows.reduce((sum, row) => sum + row.sessions, 0)

  return (
    <div className="-mx-3 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            <th scope="col" className={headClass}>Student</th>
            <th scope="col" className={`${headClass} text-right`}>Sessions</th>
            <th scope="col" className={`${headClass} text-right`}>Hours</th>
            <th scope="col" className={`${headClass} text-right`}>Revenue</th>
            <th scope="col" className={`${headClass} hidden w-1/4 sm:table-cell`}>
              <span className="sr-only">Share of revenue</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-white/5">
          {rows.map((row) => {
            const share = totalRevenue ? (row.revenue / totalRevenue) * 100 : 0
            return (
              <tr key={row.student_id}>
                <td className="px-3 py-2">
                  <Link to={`/students/${row.student_id}`} className="font-medium hover:text-blue-600 dark:hover:text-blue-400">
                    {row.student_name}
                  </Link>
                  {row.hourly_rate === null && <span className={`ml-2 ${noteClass}`}>No hourly rate</span>}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{row.sessions}</td>
                <td className="px-3 py-2 text-right tabular-nums">{row.hours.toFixed(1)}h</td>
                <td className="px-3 py-2 text-right font-medium tabular-nums">{formatMoney(row.revenue)}</td>
                <td className="hidden px-3 py-2 sm:table-cell">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                      <div className="h-full rounded-full bg-blue-500" style={{ width: `${share}%` }} />
                    </div>
                    <span className={`w-9 text-right tabular-nums ${noteClass}`}>{Math.round(share)}%</span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr className="border-t border-slate-200 font-semibold dark:border-white/10">
            <th scope="row" className="px-3 py-2 text-left">Total</th>
            <td className="px-3 py-2 text-right tabular-nums">{totalSessions}</td>
            <td className="px-3 py-2 text-right tabular-nums">{totalHours.toFixed(1)}h</td>
            <td className="px-3 py-2 text-right tabular-nums">{formatMoney(totalRevenue)}</td>
            <td className="hidden sm:table-cell" />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
