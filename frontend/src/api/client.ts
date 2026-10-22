const API_ROOT = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error { constructor(public status: number, message: string) { super(message) } }

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { credentials: 'include', ...init })
  if (!response.ok) throw new ApiError(response.status, 'requestFailed')
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const login = () => { window.location.assign(`${API_ROOT}/auth/login`) }
export const logout = () => api<void>('/auth/logout', { method: 'POST' })
