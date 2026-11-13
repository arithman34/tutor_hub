/**
 * A fake TutorHub API for tests. Each test starts logged in as `testUser`
 * unless it says otherwise, and can override any endpoint with server.use().
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Dashboard, RevenueMonth, StudentBreakdownRow, UpcomingSession, User } from '../api/types'

export const testUser: User = {
  id: '6b3f1c1e-1111-4a5a-9a0b-2c1d3e4f5a6b',
  email: 'tutor@example.com',
  first_name: 'Ada',
  last_name: 'Lovelace',
  is_active: true,
  address: null,
  is_demo: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const testDashboard: Dashboard = {
  revenue_alltime: 12345.5,
  revenue_this_month: 840,
  revenue_this_year: 9600,
  revenue_same_period_last_month: 746.67,
  revenue_projected: 1210,
  revenue_month_to_date: [0, 300, 300, 540, 840],
  mom_trend: 12.5,
  compare_from: '2026-10-01',
  compare_to: '2026-10-13',
  outstanding_total: 0,
  outstanding_payees: 0,
  average_hourly_rate: 38.4,
  hours_this_year: 250,
  active_students: 7,
  students_taught_this_month: 6,
  sessions_this_week: 5,
  sessions_week_pct_change: null,
  sessions_this_month: 18,
  sessions_pct_change: 0,
  hours_this_month: 21.5,
  hours_pct_change: -4,
}

export const testRevenueMonths: RevenueMonth[] = Array.from({ length: 12 }, (_, index) => ({
  month: `${index === 0 ? 2025 : 2026}-${String(index === 0 ? 12 : index).padStart(2, '0')}-01`,
  revenue: 700 + index * 10,
  in_progress: index === 11,
}))

export const testUpcoming: UpcomingSession[] = []

export const testStudentBreakdown: StudentBreakdownRow[] = [
  { student_id: 'a1', student_name: 'Sam Smith', sessions: 4, hours: 4, revenue: 160, hourly_rate: 40 },
  { student_id: 'b2', student_name: 'Alex Jones', sessions: 3, hours: 4.5, revenue: 135, hourly_rate: 30 },
]

export const unauthorized = () => HttpResponse.json({ detail: 'Not authenticated.' }, { status: 401 })

export const handlers = [
  http.get('*/api/v1/auth/csrf', () => HttpResponse.json({ csrf_token: 'test-csrf-token' })),
  http.get('*/api/v1/auth/me', () => HttpResponse.json(testUser)),
  http.get('*/api/v1/setup', () => HttpResponse.json({ needed: false })),
  http.post('*/api/v1/auth/cookie/refresh', unauthorized),
  http.post('*/api/v1/auth/cookie/logout', () => new HttpResponse(null, { status: 204 })),
  http.get('*/api/v1/analytics/dashboard', () => HttpResponse.json(testDashboard)),
  http.get('*/api/v1/analytics/dashboard/revenue', () => HttpResponse.json({ months: testRevenueMonths })),
  http.get('*/api/v1/analytics/dashboard/upcoming', () => HttpResponse.json({ sessions: testUpcoming })),
  http.get('*/api/v1/analytics/dashboard/students', () => HttpResponse.json({ students: testStudentBreakdown })),
  http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: false })),
]

export const server = setupServer(...handlers)
