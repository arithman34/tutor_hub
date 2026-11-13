/**
 * Light/dark mode. Stored under the same localStorage key the public pages
 * Django renders read (templates/base.html), so they match the app.
 */
import { useSyncExternalStore } from 'react'

const STORAGE_KEY = 'theme'

function isDark(): boolean {
  return document.documentElement.classList.contains('dark')
}

/** Calls `onChange` whenever the .dark class on <html> comes or goes. */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  return () => observer.disconnect()
}

/**
 * Whether dark mode is on. Every component using this re-renders when it's
 * toggled, which matters for anything coloured from JavaScript (charts).
 */
export function useIsDark(): boolean {
  return useSyncExternalStore(subscribe, isDark)
}

export function useTheme() {
  const dark = useIsDark()

  function toggle() {
    const next = !isDark()
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light')
    } catch {
      // Storage can be blocked (private windows); the toggle still works for this page.
    }
  }

  return { dark, toggle }
}
