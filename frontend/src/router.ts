// A tiny History-API router: the app only has a couple of routes, so no extra dependency.
import { useSyncExternalStore } from 'react'

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  window.addEventListener('popstate', listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('popstate', listener)
  }
}

// The folder the app is served from: '/' locally and on Vercel, '/hype-scandal-backtest/' on GitHub Pages
// (set by `base` in vite.config.ts). Routes in the app are written without it, e.g. '/backtest'.
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '')

/** '/backtest' -> '/hype-scandal-backtest/backtest' on Pages; unchanged elsewhere. */
export function withBase(to: string): string {
  return to.startsWith('/') ? BASE + to : to
}

/** '/hype-scandal-backtest/backtest' -> '/backtest'; the inverse of withBase. */
function stripBase(path: string): string {
  if (BASE && (path === BASE || path.startsWith(BASE + '/'))) return path.slice(BASE.length) || '/'
  return path
}

const snapshot = () => window.location.pathname + window.location.search

export function navigate(to: string, { replace = false } = {}) {
  if (replace) window.history.replaceState(null, '', withBase(to))
  else window.history.pushState(null, '', withBase(to))
  listeners.forEach((listener) => listener())
  if (!replace) window.scrollTo(0, 0)
}

/** Current path and query; re-renders on navigation. */
export function useLocation(): { path: string; query: URLSearchParams } {
  const href = useSyncExternalStore(subscribe, snapshot)
  const url = new URL(href, window.location.origin)
  return { path: stripBase(url.pathname), query: url.searchParams }
}
