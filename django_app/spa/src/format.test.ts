import { describe, expect, it } from 'vitest'

import { formatDate, toWallIso, wallDate, wallTime } from './format'

describe('wall-clock session times', () => {
  it('reads the stored UTC fields as-is, without converting to local time', () => {
    // A 23:30 lesson in July is stored as 23:30Z. In London that instant is
    // 00:30 the next day, which must not leak into what we show.
    expect(wallDate('2026-07-14T23:30:00Z')).toBe('2026-07-14')
    expect(wallTime('2026-07-14T23:30:00Z')).toBe('23:30')
    expect(formatDate('2026-07-14T23:30:00Z')).toBe('14/07/2026')
  })

  it('normalises other offsets the API might send to UTC first', () => {
    expect(wallTime('2026-07-14T17:30:00+01:00')).toBe('16:30')
  })

  it('round-trips a typed date and time', () => {
    const iso = toWallIso('2026-03-05', '16:00')
    expect(iso).toBe('2026-03-05T16:00:00Z')
    expect([wallDate(iso), wallTime(iso)]).toEqual(['2026-03-05', '16:00'])
  })

  it('formats plain dates too', () => {
    expect(formatDate('2026-03-05')).toBe('05/03/2026')
  })
})
