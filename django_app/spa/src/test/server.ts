/**
 * A fake TutorHub API for tests. Each test starts logged in as `testUser`
 * unless it says otherwise, and can override any endpoint with server.use().
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Dashboard, User } from '../api/types'

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
  mom_trend: 12.5,
  outstanding_total: 0,
  outstanding_payees: 0,
  active_students: 7,
  sessions_this_week: 5,
  sessions_this_month: 18,
  sessions_pct_change: null,
  hours_this_month: 21.5,
  hours_pct_change: -4,
}

export const unauthorized = () => HttpResponse.json({ detail: 'Not authenticated.' }, { status: 401 })

export const handlers = [
  http.get('*/api/v1/auth/csrf', () => HttpResponse.json({ csrf_token: 'test-csrf-token' })),
  http.get('*/api/v1/auth/me', () => HttpResponse.json(testUser)),
  http.get('*/api/v1/setup', () => HttpResponse.json({ needed: false })),
  http.post('*/api/v1/auth/cookie/refresh', unauthorized),
  http.post('*/api/v1/auth/cookie/logout', () => new HttpResponse(null, { status: 204 })),
  http.get('*/api/v1/analytics/dashboard', () => HttpResponse.json(testDashboard)),
  http.get('*/api/v1/zoom/status', () => HttpResponse.json({ connected: false })),
]

export const server = setupServer(...handlers)
