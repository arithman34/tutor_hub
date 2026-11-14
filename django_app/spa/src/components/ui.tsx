/**
 * Building blocks every page shares. The classes they use (.card, .btn,
 * .badge…) live in frontend/theme.css, which the public pages use too.
 */
import { ChevronLeft, Inbox, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

/** The page title row: optional back arrow, title and description, actions on the right. */
export function PageHeader({
  title,
  description,
  backTo,
  children,
}: {
  title: ReactNode
  description?: ReactNode
  backTo?: string
  children?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-3">
      {backTo && (
        <Link
          to={backTo}
          aria-label="Back"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 shadow-xs hover:text-slate-900 dark:border-white/10 dark:bg-slate-800 dark:text-slate-400 dark:hover:text-white"
        >
          <ChevronLeft aria-hidden="true" className="h-4 w-4" />
        </Link>
      )}
      <div className="min-w-0">
        <h1 className="page-title">{title}</h1>
        {description && <p className="muted mt-0.5 text-sm">{description}</p>}
      </div>
      {children && <div className="ml-auto flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  )
}

/** A card with a title row, for a section of a page. */
export function Section({
  title,
  description,
  action,
  children,
  className = '',
  bodyClassName = 'p-5',
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={`card ${className}`}>
      <div className="card-header">
        <div className="min-w-0">
          <h2 className="section-title">{title}</h2>
          {description && <p className="muted mt-0.5 text-xs">{description}</p>}
        </div>
        {action}
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

/** What to show where a list would be when there's nothing in it. */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  titleAs: Title = 'p',
  children,
}: {
  icon?: LucideIcon
  title: string
  titleAs?: 'p' | 'h1' | 'h2'
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-500">
        <Icon aria-hidden="true" className="h-5 w-5" />
      </span>
      <Title className="font-medium text-slate-700 dark:text-slate-200">{title}</Title>
      {children && <div className="muted max-w-sm text-sm">{children}</div>}
    </div>
  )
}

export function StatusBadge({ active }: { active: boolean }) {
  return active ? <span className="badge badge-green">Active</span> : <span className="badge badge-slate">Inactive</span>
}

export function ErrorMessage({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="alert alert-error">
      {children}
    </p>
  )
}

export function Loading({ children = 'Loading…' }: { children?: ReactNode }) {
  return (
    <p className="muted flex items-center gap-2 text-sm">
      <span aria-hidden="true" className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      {children}
    </p>
  )
}

/** The TutorHub logo: a blue tile and the name. */
export function Brand({ className = '' }: { className?: string }) {
  return (
    <span className={`brand ${className}`}>
      <span aria-hidden="true" className="brand-mark">
        T
      </span>
      TutorHub
    </span>
  )
}

export const buttonPrimary = 'btn btn-primary'
export const buttonSecondary = 'btn btn-secondary'
export const buttonDanger = 'btn btn-danger'
