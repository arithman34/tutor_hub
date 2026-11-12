import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'

import { Loading } from './components/ui'
import { RequireAuth } from './RequireAuth'
import { AppLayout } from './layout/AppLayout'
import { AssistantPage } from './pages/assistant/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { NewPayeePage } from './pages/payees/NewPayeePage'
import { PayeeDetailPage } from './pages/payees/PayeeDetailPage'
import { PayeesPage } from './pages/payees/PayeesPage'
import { NewPaymentPage } from './pages/payments/NewPaymentPage'
import { PaymentsPage } from './pages/payments/PaymentsPage'
import { NewSessionPage } from './pages/sessions/NewSessionPage'
import { SessionDetailPage } from './pages/sessions/SessionDetailPage'
import { SessionsPage } from './pages/sessions/SessionsPage'
import { NewStudentPage } from './pages/students/NewStudentPage'
import { StudentDetailPage } from './pages/students/StudentDetailPage'
import { StudentsPage } from './pages/students/StudentsPage'

// Analytics brings in Chart.js, which no other page needs. Loading it lazily
// splits it into its own bundle, downloaded only when Analytics is opened.
const AnalyticsPage = lazy(() => import('./pages/analytics/AnalyticsPage').then((module) => ({ default: module.AnalyticsPage })))

/** Every page in the app. Paths are relative to /app (see main.tsx). */
export function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route
            path="analytics"
            element={
              <Suspense fallback={<Loading>Loading analytics…</Loading>}>
                <AnalyticsPage />
              </Suspense>
            }
          />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="students" element={<StudentsPage />} />
          <Route path="students/new" element={<NewStudentPage />} />
          <Route path="students/:studentId" element={<StudentDetailPage />} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="sessions/new" element={<NewSessionPage />} />
          <Route path="sessions/:sessionId" element={<SessionDetailPage />} />
          <Route path="payees" element={<PayeesPage />} />
          <Route path="payees/new" element={<NewPayeePage />} />
          <Route path="payees/:payeeId" element={<PayeeDetailPage />} />
          <Route path="payments" element={<PaymentsPage />} />
          <Route path="payments/new" element={<NewPaymentPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
