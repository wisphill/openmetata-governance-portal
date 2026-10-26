const API_ROOT = import.meta.env.VITE_API_URL ?? ''
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'

export class ApiError extends Error { constructor(public status: number, message: string) { super(message) } }

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  if (USE_MOCKS) { const { mockApi } = await import('../mocks'); return mockApi<T>(path, init) }
  const response = await fetch(`${API_ROOT}${path}`, { credentials: 'include', ...init })
  if (!response.ok) {
    const body = await response.json().catch(() => undefined) as { detail?: unknown; message?: unknown } | undefined
    const message = typeof body?.detail === 'string' ? body.detail : typeof body?.message === 'string' ? body.message : 'requestFailed'
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const login = () => { if (USE_MOCKS) window.location.reload(); else window.location.assign(`${API_ROOT}/auth/login`) }
export const logout = () => api<void>('/auth/logout', { method: 'POST' })
