import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, postJson } from './api'
import type { Me, User } from './types'

type AuthValue = {
  me: Me | null
  user: User | null
  loading: boolean
  refresh: () => Promise<void>
  login: (door: string, email: string, password: string, turnstile?: string) => Promise<string>
  logout: () => Promise<void>
  setLook: (theme: string, density: string) => Promise<void>
  setView: (view: string) => Promise<void>
}

const AuthCtx = createContext<AuthValue | null>(null)

function applyLook(theme: string, density: string) {
  document.documentElement.setAttribute('data-theme', theme)
  document.documentElement.setAttribute('data-density', density)
  try {
    localStorage.setItem('aa.theme', theme)
    localStorage.setItem('aa.density', density)
  } catch {
    /* ignore */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    const data = await api<Me>('/api/me')
    setMe(data)
    const theme = data.user?.theme || 'ascendancy'
    const density = data.user?.density || 'cozy'
    applyLook(theme, density)
  }

  useEffect(() => {
    refresh().catch(() => setMe(null)).finally(() => setLoading(false))
  }, [])

  const value = useMemo<AuthValue>(
    () => ({
      me,
      user: me?.user ?? null,
      loading,
      refresh,
      login: async (door, email, password, turnstile = '') => {
        const data = await postJson<{ next: string }>('/api/login', { door, email, password, turnstile })
        await refresh()
        return data.next
      },
      logout: async () => {
        await postJson('/api/logout', {})
        await refresh()
      },
      setLook: async (theme, density) => {
        applyLook(theme, density)
        await postJson('/api/theme', { theme, density, csrf: me?.user?.csrf || '' })
        await refresh()
      },
      setView: async (view) => {
        await postJson('/api/view', { view, csrf: me?.user?.csrf || '' })
        await refresh()
      },
    }),
    [me, loading],
  )

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('Auth missing')
  return ctx
}
