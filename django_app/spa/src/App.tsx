import { Route, Routes } from 'react-router'

import { RequireAuth } from './RequireAuth'
import { AppLayout } from './layout/AppLayout'
import { AssistantPage } from './pages/assistant/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { NewStudentPage } from './pages/students/NewStudentPage'
import { StudentDetailPage } from './pages/students/StudentDetailPage'
import { StudentsPage } from './pages/students/StudentsPage'

/** Every page in the app. Paths are relative to /app (see main.tsx). */
export function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="students" element={<StudentsPage />} />
          <Route path="students/new" element={<NewStudentPage />} />
          <Route path="students/:studentId" element={<StudentDetailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
