const gbp = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' })

export function formatMoney(amount: number): string {
  return gbp.format(amount)
}

const ukDate = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Europe/London' })

/** An ISO date-time as 31/01/2026, in UK time. */
export function formatDate(iso: string): string {
  return ukDate.format(new Date(iso))
}

/** "+12.5% vs last month", or null when there's nothing to compare with. */
export function formatChange(percent: number | null | undefined, period = 'last month'): string | null {
  if (percent === null || percent === undefined) return null
  const sign = percent > 0 ? '+' : ''
  return `${sign}${percent}% vs ${period}`
}
