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

/*
 * Session times are "wall-clock" times. TutorHub stores the time you typed
 * (or the Google Calendar event's local time) as if it were UTC: a 16:00
 * lesson in July is saved as 16:00Z, not 15:00Z. Every existing session uses
 * this convention, so these helpers read and write the UTC fields directly
 * and never convert to the browser's timezone, which would shift summer
 * lessons by an hour (and late-evening ones onto the next day).
 */

/** "2026-03-05" from "2026-03-05T16:00:00Z". */
export function wallDate(iso: string): string {
  return iso.slice(0, 10)
}

/** "16:00" from "2026-03-05T16:00:00Z". */
export function wallTime(iso: string): string {
  return new Date(iso).toISOString().slice(11, 16)
}

/** The ISO timestamp the API expects for a wall-clock date and time. */
export function toWallIso(date: string, time: string): string {
  return `${date}T${time}:00Z`
}

/** "05/03/2026" from a "2026-03-05" date or an ISO timestamp. */
export function formatDate(isoOrDate: string): string {
  const date = isoOrDate.length === 10 ? isoOrDate : wallDate(new Date(isoOrDate).toISOString())
  const [year, month, day] = date.split('-')
  return `${day}/${month}/${year}`
}
