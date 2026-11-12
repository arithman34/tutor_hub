const gbp = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' })

export function formatMoney(amount: number): string {
  return gbp.format(amount)
}

/** "+12.5% vs last month", or null when there's nothing to compare with. */
export function formatChange(percent: number | null | undefined, period = 'last month'): string | null {
  if (percent === null || percent === undefined) return null
  const sign = percent > 0 ? '+' : ''
  return `${sign}${percent}% vs ${period}`
}
