import type { ReactNode } from 'react'

import { Brand } from './ui'

/**
 * The frame for pages outside the app (signing in, first-time setup): the
 * logo, a card with a title, and the privacy policy link underneath. The
 * homepage Django renders uses the same brand and card styles.
 */
export function AuthLayout({ title, description, children }: { title: string; description?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <a href="/" className="mb-8">
        <Brand />
      </a>
      <div className="card w-full max-w-md p-8 hover:border-slate-200 dark:hover:border-white/5">
        <h1 className="text-center text-xl font-bold tracking-tight">{title}</h1>
        {description && <p className="muted mt-1 text-center text-sm">{description}</p>}
        <div className="mt-6">{children}</div>
      </div>
      <a href="/privacy" className="muted mt-6 text-sm hover:text-slate-900 dark:hover:text-white">
        Privacy policy
      </a>
    </div>
  )
}
