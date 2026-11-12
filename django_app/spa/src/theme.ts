/**
 * Light/dark mode. Stored under the same localStorage key the public pages
 * Django renders read (templates/base.html), so they match the app.
 */
import { useState } from 'react'

const STORAGE_KEY = 'theme'

function isDark(): boolean {
  return document.documentElement.classList.contains('dark')
}

export function useTheme() {
  const [dark, setDark] = useState(isDark)

  function toggle() {
    const next = !isDark()
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light')
    } catch {
      // Storage can be blocked (private windows); the toggle still works for this page.
    }
    setDark(next)
  }

  return { dark, toggle }
}
