/**
 * Light/dark mode. Stored under the same localStorage key as the classic
 * pages, so the choice carries across both while they live side by side.
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
