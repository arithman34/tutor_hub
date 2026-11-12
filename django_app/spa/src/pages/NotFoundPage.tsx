import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="text-sm text-gray-600 dark:text-gray-300">This page doesn't exist in the new app yet.</p>
      <Link to="/" className="text-sm text-blue-600 underline dark:text-blue-400">
        Back to the dashboard
      </Link>
    </div>
  )
}
