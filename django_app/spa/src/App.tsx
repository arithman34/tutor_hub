import { Route, Routes } from 'react-router'

import { RequireAuth } from './RequireAuth'
import { AppLayout } from './layout/AppLayout'
import { AssistantPage } from './pages/assistant/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'

/** Every page in the app. Paths are relative to /app (see main.tsx). */
export function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
