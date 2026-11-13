const gbp = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' })
const gbpWhole = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 0 })
const longDate = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatMoney(amount: number): string {
  return gbp.format(amount)
}

/** A balance with its sign always shown: "+£20.00", "-£12.50". */
export function formatBalance(amount: number): string {
  return `${amount < 0 ? '-' : '+'}${formatMoney(Math.abs(amount))}`
}

/** Red when money is owed, green when in credit, grey when settled. */
export function balanceTone(amount: number): string {
  if (amount < 0) return 'text-red-600 dark:text-red-400'
  if (amount > 0) return 'text-green-600 dark:text-green-400'
  return 'text-gray-500 dark:text-gray-400'
}

/** "£1,235", for whole-pound figures like a projection or a chart axis. */
export function formatMoneyRounded(amount: number): string {
  return gbpWhole.format(amount)
}

/** "1–13 Oct", or "1 Oct" for a single day, from two "2026-10-01" dates. */
export function formatDayRange(from: string, to: string): string {
  const [, , fromDay] = from.split('-')
  const [, toMonth, toDay] = to.split('-')
  const month = SHORT_MONTHS[Number(toMonth) - 1]
  return fromDay === toDay ? `${Number(toDay)} ${month}` : `${Number(fromDay)}–${Number(toDay)} ${month}`
}

/** "Friday 13 November 2026" for a local Date. */
export function formatLongDate(date: Date): string {
  return longDate.format(date)
}

/** "2026-11-13" for a local Date: the same form as wallDate(). */
export function localDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
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
