import {
  ChartColumn,
  CreditCard,
  Database,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  NotebookPen,
  Plug,
  Sparkles,
  Sun,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { Suspense, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { useLogout, useMe } from '../auth'
import { Brand, Loading } from '../components/ui'
import { useTheme } from '../theme'

type NavItem = { label: string; to: string; icon: LucideIcon }

const NAV_SECTIONS: { title?: string; items: NavItem[] }[] = [
  {
    items: [
      { label: 'Dashboard', to: '/', icon: LayoutDashboard },
      { label: 'Analytics', to: '/analytics', icon: ChartColumn },
      { label: 'TutorHub AI', to: '/assistant', icon: Sparkles },
      { label: 'Students', to: '/students', icon: GraduationCap },
      { label: 'Sessions', to: '/sessions', icon: NotebookPen },
    ],
  },
  {
    title: 'Integrations',
    items: [
      { label: 'Connections', to: '/connections', icon: Plug },
      { label: 'Payments', to: '/payments', icon: CreditCard },
      { label: 'Payees', to: '/payees', icon: Users },
    ],
  },
  { title: 'Account', items: [{ label: 'My Data', to: '/data', icon: Database }] },
]

const itemClass =
  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-200/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'
const activeClass = 'bg-blue-50 font-medium text-blue-700 dark:bg-slate-800 dark:text-white'
const iconClass = 'h-4 w-4 shrink-0'
const iconButton =
  'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 disabled:opacity-50 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white'

function NavItemLink({ item, onNavigate }: { item: NavItem; onNavigate: () => void }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onNavigate}
      className={({ isActive }) => `${itemClass} ${isActive ? activeClass : ''}`}
    >
      {({ isActive }) => (
        <>
          <item.icon aria-hidden="true" className={`${iconClass} ${isActive ? 'text-blue-600 dark:text-blue-400' : ''}`} />
          {item.label}
        </>
      )}
    </NavLink>
  )
}

export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { dark, toggle } = useTheme()
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  const name = me.data ? `${me.data.first_name} ${me.data.last_name}` : 'Profile'
  const initials = me.data ? `${me.data.first_name[0] ?? ''}${me.data.last_name[0] ?? ''}`.toUpperCase() : '?'

  function handleLogout() {
    logout.mutate(undefined, { onSuccess: () => navigate('/login', { replace: true }) })
  }

  return (
    <div className="min-h-screen sm:flex">
      <button
        type="button"
        onClick={() => setMenuOpen(true)}
        className="fixed top-4 left-4 z-30 inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white sm:hidden"
        aria-label="Open menu"
      >
        <Menu aria-hidden="true" className="h-4 w-4" />
        Menu
      </button>

      {menuOpen && (
        <div className="fixed inset-0 z-30 bg-slate-950/60 sm:hidden" onClick={() => setMenuOpen(false)} aria-hidden="true" />
      )}

      {/* Same colour as the page in light mode and a shade darker in dark mode,
          set apart by a 1px border rather than a lighter panel. */}
      <aside
        aria-label="Sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-slate-50 transition-transform sm:sticky sm:top-0 sm:h-screen sm:translate-x-0 dark:border-slate-800 dark:bg-slate-950 ${
          menuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Brand />
          <button type="button" onClick={() => setMenuOpen(false)} className={`${iconButton} sm:hidden`} aria-label="Close menu">
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-3">
          {NAV_SECTIONS.map((section, index) => (
            <div key={section.title ?? index}>
              {section.title && (
                <p className="px-3 pb-1.5 text-xs font-medium tracking-[0.04em] text-slate-500 uppercase dark:text-slate-500">
                  {section.title}
                </p>
              )}
              <ul className="space-y-0.5">
                {section.items.map((item) => (
                  <li key={item.label}>
                    <NavItemLink item={item} onNavigate={() => setMenuOpen(false)} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="space-y-1 border-t border-slate-200 px-3 py-3 dark:border-slate-800">
          <button type="button" onClick={handleLogout} disabled={logout.isPending} className={`${itemClass} w-full disabled:opacity-50`}>
            <LogOut aria-hidden="true" className={iconClass} />
            Sign out
          </button>
          <div className="flex items-center gap-1">
            <NavLink
              to="/profile"
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm font-medium hover:bg-slate-200/60 dark:hover:bg-slate-800 ${
                  isActive ? 'bg-blue-50 text-blue-700 dark:bg-slate-800 dark:text-white' : 'text-slate-700 dark:text-slate-200'
                }`
              }
            >
              <span
                aria-hidden="true"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white"
              >
                {initials}
              </span>
              <span className="truncate">{name}</span>
            </NavLink>
            <button type="button" onClick={toggle} className={iconButton} aria-label={dark ? 'Light mode' : 'Dark mode'} title={dark ? 'Light mode' : 'Dark mode'}>
              {dark ? <Sun aria-hidden="true" className="h-4 w-4" /> : <Moon aria-hidden="true" className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 pt-16 pb-8 sm:px-8 sm:pt-8">
        <div className="mx-auto w-full max-w-[1500px]">
          {me.data?.is_demo && (
            <p role="status" className="alert alert-warning mb-6">
              You're looking round the demo. Every student, lesson and payment is made up, and it's read-only, so nothing you
              change will be saved.
            </p>
          )}
          {/* Most pages load on first visit (see App.tsx); keep the sidebar while they do. */}
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  )
}
