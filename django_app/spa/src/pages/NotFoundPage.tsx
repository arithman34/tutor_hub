import { Compass } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState, buttonPrimary } from '../components/ui'

export function NotFoundPage() {
  return (
    <div className="card mx-auto mt-10 max-w-lg">
      <EmptyState icon={Compass} title="Page not found" titleAs="h1">
        <p>This page doesn't exist in the app.</p>
        <Link to="/" className={`${buttonPrimary} mt-4`}>
          Back to the dashboard
        </Link>
      </EmptyState>
    </div>
  )
}
