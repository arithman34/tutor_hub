import { Suspense, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { useLogout, useMe } from '../auth'
import { Loading } from '../components/ui'
import { useTheme } from '../theme'

type NavItem = { label: string; to: string }

const NAV_SECTIONS: { title?: string; items: NavItem[] }[] = [
  {
    items: [
      { label: 'Dashboard', to: '/' },
      { label: 'Analytics', to: '/analytics' },
      { label: 'TutorHub AI', to: '/assistant' },
      { label: 'Students', to: '/students' },
      { label: 'Sessions', to: '/sessions' },
    ],
  },
  {
    title: 'Integrations',
    items: [
      { label: 'Connections', to: '/connections' },
      { label: 'Payments', to: '/payments' },
      { label: 'Payees', to: '/payees' },
    ],
  },
  { title: 'Account', items: [{ label: 'My Data', to: '/data' }] },
]

const itemClass = 'block rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-blue-600 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-blue-400'
const activeClass = 'bg-blue-50 font-medium text-blue-700 dark:bg-gray-700 dark:text-blue-400'

function NavItemLink({ item, onNavigate }: { item: NavItem; onNavigate: () => void }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/'}
      onClick={onNavigate}
      className={({ isActive }) => `${itemClass} ${isActive ? activeClass : ''}`}
    >
      {item.label}
    </NavLink>
  )
}

export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { dark, toggle } = useTheme()
  const me = useMe()
  const logout = useLogout()
  const navigate = useNavigate()

  function handleLogout() {
    logout.mutate(undefined, { onSuccess: () => navigate('/login', { replace: true }) })
  }

  return (
    <div className="min-h-screen sm:flex">
      <button
        type="button"
        onClick={() => setMenuOpen(true)}
        className="fixed top-4 left-4 z-30 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white sm:hidden"
        aria-label="Open menu"
      >
        Menu
      </button>

      {menuOpen && (
        <div className="fixed inset-0 z-30 bg-gray-900/50 sm:hidden" onClick={() => setMenuOpen(false)} aria-hidden="true" />
      )}

      <aside
        aria-label="Sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white transition-transform sm:sticky sm:top-0 sm:h-screen sm:translate-x-0 dark:border-gray-700 dark:bg-gray-800 ${
          menuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <span className="text-lg font-bold text-blue-600 dark:text-blue-400">TutorHub</span>
          <button
            type="button"
            onClick={() => setMenuOpen(false)}
            className="text-gray-500 sm:hidden dark:text-gray-400"
            aria-label="Close menu"
          >
            ✕
          </button>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3">
          {NAV_SECTIONS.map((section, index) => (
            <div key={section.title ?? index}>
              {section.title && (
                <p className="px-3 pb-1 text-xs font-medium tracking-wider text-gray-500 uppercase dark:text-gray-400">
                  {section.title}
                </p>
              )}
              <ul className="space-y-1">
                {section.items.map((item) => (
                  <li key={item.label}>
                    <NavItemLink item={item} onNavigate={() => setMenuOpen(false)} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="space-y-1 border-t border-gray-200 px-3 py-4 dark:border-gray-700">
          <button type="button" onClick={toggle} className={`${itemClass} w-full text-left`}>
            {dark ? 'Light mode' : 'Dark mode'}
          </button>
          <NavLink
            to="/profile"
            onClick={() => setMenuOpen(false)}
            className={({ isActive }) => `${itemClass} ${isActive ? activeClass : ''}`}
          >
            {me.data ? `${me.data.first_name} ${me.data.last_name}` : 'Profile'}
          </NavLink>
          <button
            type="button"
            onClick={handleLogout}
            disabled={logout.isPending}
            className={`${itemClass} w-full text-left disabled:opacity-50`}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 px-4 pt-16 pb-8 sm:px-8 sm:pt-8">
        {me.data?.is_demo && (
          <p role="status" className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
            You're looking round the demo. Every student, lesson and payment is made up, and it's read-only, so nothing you
            change will be saved.
          </p>
        )}
        {/* Most pages load on first visit (see App.tsx); keep the sidebar while they do. */}
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
