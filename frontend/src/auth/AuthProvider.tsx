import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react'
import { ApiError, api, logout as endSession } from '../api/client'
import type { Me } from '../types/api'

type AuthState = { me?: Me; loading: boolean; refresh: () => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: PropsWithChildren) {
  const [me, setMe] = useState<Me>()
  const [loading, setLoading] = useState(true)
  const refresh = async () => {
    setLoading(true)
    try { setMe(await api<Me>('/api/me')) } catch (error) { if (!(error instanceof ApiError) || error.status !== 401) setMe(undefined) } finally { setLoading(false) }
  }
  useEffect(() => { void refresh() }, [])
  const logout = async () => { await endSession(); setMe(undefined) }
  return <AuthContext.Provider value={{ me, loading, refresh, logout }}>{children}</AuthContext.Provider>
}
export const useAuth = () => { const state = useContext(AuthContext); if (!state) throw new Error('AuthProvider is required'); return state }
