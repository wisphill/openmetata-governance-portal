import type { TaskPage } from '../types/api'
import { mockMe } from './me'
import { mockTasks } from './tasks'

const LATENCY_MS = 300

export async function mockApi<T>(path: string, init?: RequestInit): Promise<T> {
  await new Promise(resolve => setTimeout(resolve, LATENCY_MS))
  const url = new URL(path, window.location.origin)
  if (url.pathname === '/api/me') return mockMe as T
  if (url.pathname === '/auth/logout' && init?.method === 'POST') return undefined as T
  if (url.pathname === '/api/tasks') {
    const status = url.searchParams.get('status')
    const type = url.searchParams.get('type')
    const items = mockTasks.filter(task => (!status || task.status === status) && (!type || task.type === type))
    const page: TaskPage = { items, page: 1, page_size: items.length, total: items.length }
    return page as T
  }
  throw new Error(`No mock registered for ${path}`)
}
