import type { ReactNode } from 'react'
import { Link } from 'react-router'

/** The page title row, with an optional back arrow and actions on the right. */
export function PageHeader({ title, backTo, children }: { title: ReactNode; backTo?: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      {backTo && (
        <Link to={backTo} aria-label="Back" className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
      )}
      <h1 className="text-2xl font-bold">{title}</h1>
      {children && <div className="ml-auto flex flex-wrap items-center gap-3">{children}</div>}
    </div>
  )
}

export function StatusBadge({ active }: { active: boolean }) {
  return active ? (
    <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/50 dark:text-green-300">
      Active
    </span>
  ) : (
    <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/50 dark:text-red-300">
      Inactive
    </span>
  )
}

export function ErrorMessage({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
      {children}
    </p>
  )
}

export function Loading({ children = 'Loading…' }: { children?: ReactNode }) {
  return <p className="text-sm text-gray-500 dark:text-gray-400">{children}</p>
}

export const buttonPrimary =
  'rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60'
export const buttonSecondary =
  'rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-60 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'
export const buttonDanger =
  'rounded-lg border border-red-300 px-4 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-60 dark:hover:bg-red-900/20'
