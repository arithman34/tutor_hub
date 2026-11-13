import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { ReactNode } from 'react'

/** Small uppercase label shared by cards and panels. */
export const labelClass = 'text-xs font-medium tracking-[0.04em] text-slate-500 uppercase dark:text-slate-400'

/** Secondary-line text colour. */
export const noteClass = 'text-xs text-slate-500 dark:text-slate-400'

/**
 * "▲ 25% vs 1–13 Oct". Up is green and down is amber rather than red: a
 * quieter week isn't an error. The light theme uses a shade darker of each so
 * the text stays readable on white.
 */
export function Delta({ percent, period }: { percent: number | null | undefined; period: string }) {
  if (percent === null || percent === undefined) {
    return <span className={noteClass}>Nothing to compare with {period}</span>
  }
  const Icon = percent > 0 ? ArrowUpRight : percent < 0 ? ArrowDownRight : Minus
  const tone =
    percent > 0 ? 'text-green-600 dark:text-[#22c55e]' : percent < 0 ? 'text-amber-600 dark:text-[#f59e0b]' : 'text-slate-500 dark:text-slate-400'
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span className={`inline-flex items-center gap-0.5 font-medium tabular-nums ${tone}`}>
        <Icon aria-hidden="true" className="h-3.5 w-3.5" strokeWidth={2.5} />
        <span className="sr-only">{percent > 0 ? 'Up' : percent < 0 ? 'Down' : 'No change'}</span>
        {Math.abs(percent)}%
      </span>
      <span className="text-slate-500 dark:text-slate-400">vs {period}</span>
    </span>
  )
}

export function StatCard({ label, value, note, className = '' }: { label: string; value: ReactNode; note: ReactNode; className?: string }) {
  return (
    // A column, with the note pinned to the bottom, so cards stretched to the
    // hero card's height in the money row still line up.
    <div className={`card flex flex-col px-4 py-3 ${className}`}>
      <p className={labelClass}>{label}</p>
      <p className="mt-1 text-2xl leading-tight font-semibold tabular-nums">{value}</p>
      <div className="mt-auto min-h-4 pt-1 leading-4">{note}</div>
    </div>
  )
}
