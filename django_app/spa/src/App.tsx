import { lazy, Suspense, type ComponentType } from 'react'
import { Route, Routes } from 'react-router'

import { Loading } from './components/ui'
import { RequireAuth } from './RequireAuth'
import { AppLayout } from './layout/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'

/**
 * A page loaded only when it's first opened, as its own bundle. Pages export
 * named components, which React.lazy wants as a default export.
 */
function page<Name extends string>(load: () => Promise<Record<Name, ComponentType>>, name: Name) {
  return lazy(() => load().then((module) => ({ default: module[name] })))
}

// Login and the dashboard are where every visit starts, so they're in the
// main bundle; everything else (Analytics and its Chart.js above all) loads on demand.
const AnalyticsPage = page(() => import('./pages/analytics/AnalyticsPage'), 'AnalyticsPage')
const AssistantPage = page(() => import('./pages/assistant/AssistantPage'), 'AssistantPage')
const StudentsPage = page(() => import('./pages/students/StudentsPage'), 'StudentsPage')
const NewStudentPage = page(() => import('./pages/students/NewStudentPage'), 'NewStudentPage')
const StudentDetailPage = page(() => import('./pages/students/StudentDetailPage'), 'StudentDetailPage')
const SessionsPage = page(() => import('./pages/sessions/SessionsPage'), 'SessionsPage')
const NewSessionPage = page(() => import('./pages/sessions/NewSessionPage'), 'NewSessionPage')
const ScheduleSessionPage = page(() => import('./pages/sessions/ScheduleSessionPage'), 'ScheduleSessionPage')
const SessionDetailPage = page(() => import('./pages/sessions/SessionDetailPage'), 'SessionDetailPage')
const PayeesPage = page(() => import('./pages/payees/PayeesPage'), 'PayeesPage')
const NewPayeePage = page(() => import('./pages/payees/NewPayeePage'), 'NewPayeePage')
const PayeeDetailPage = page(() => import('./pages/payees/PayeeDetailPage'), 'PayeeDetailPage')
const PaymentsPage = page(() => import('./pages/payments/PaymentsPage'), 'PaymentsPage')
const NewPaymentPage = page(() => import('./pages/payments/NewPaymentPage'), 'NewPaymentPage')
const ConnectionsPage = page(() => import('./pages/connections/ConnectionsPage'), 'ConnectionsPage')
const MyDataPage = page(() => import('./pages/data/MyDataPage'), 'MyDataPage')
const ProfilePage = page(() => import('./pages/profile/ProfilePage'), 'ProfilePage')
const SetupPage = page(() => import('./pages/setup/SetupPage'), 'SetupPage')

/** Every page in the app. Paths are relative to /app (see main.tsx). */
export function App() {
  return (
    // Pages inside the layout have their own fallback there, so the sidebar
    // stays put while they load; this one covers the pages outside it.
    <Suspense fallback={<Loading>Loading…</Loading>}>
      <Routes>
        <Route path="login" element={<LoginPage />} />
        <Route path="setup" element={<SetupPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="assistant" element={<AssistantPage />} />
            <Route path="students" element={<StudentsPage />} />
            <Route path="students/new" element={<NewStudentPage />} />
            <Route path="students/:studentId" element={<StudentDetailPage />} />
            <Route path="sessions" element={<SessionsPage />} />
            <Route path="sessions/new" element={<NewSessionPage />} />
            <Route path="sessions/schedule" element={<ScheduleSessionPage />} />
            <Route path="sessions/:sessionId" element={<SessionDetailPage />} />
            <Route path="payees" element={<PayeesPage />} />
            <Route path="payees/new" element={<NewPayeePage />} />
            <Route path="payees/:payeeId" element={<PayeeDetailPage />} />
            <Route path="payments" element={<PaymentsPage />} />
            <Route path="payments/new" element={<NewPaymentPage />} />
            <Route path="connections" element={<ConnectionsPage />} />
            <Route path="data" element={<MyDataPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}
