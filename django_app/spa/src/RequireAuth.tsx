import { Navigate, Outlet, useLocation } from 'react-router'

import { useMe } from './auth'

/** Wraps the routes that need a login, sending everyone else to /login. */
export function RequireAuth() {
  const me = useMe()
  const location = useLocation()

  if (me.isPending) {
    return <p className="p-8 text-sm text-gray-500 dark:text-gray-400">Loading…</p>
  }
  if (me.isError) {
    return (
      <p role="alert" className="p-8 text-sm text-red-600 dark:text-red-400">
        Couldn't reach TutorHub. Check your connection and reload the page.
      </p>
    )
  }
  if (me.data === null) {
    // Remember where they were going, so login can send them back there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
