import type { TrendSeries } from '../../api/types'
import { formatMoney } from '../../format'

export function formatValue(value: number, unit: TrendSeries['unit']): string {
  if (unit === 'currency') return formatMoney(value)
  if (unit === 'hours') return `${value.toFixed(1)}h`
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** A bucket's start as "Mar 26" (months) or "05 Mar" (days, weeks). Buckets are UTC. */
export function bucketLabel(iso: string, granularity: string): string {
  const date = new Date(iso)
  return granularity === 'month'
    ? date.toLocaleDateString('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' })
    : date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' })
}
