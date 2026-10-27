import { ApiError } from '../api/client'
import type { AccessRequestCreated, CatalogPage, TaskPage, UserAccessAudit } from '../types/api'
import { mockMe } from './me'
import { mockTasks } from './tasks'

const LATENCY_MS = 300

export async function mockApi<T>(path: string, init?: RequestInit): Promise<T> {
  await new Promise(resolve => setTimeout(resolve, LATENCY_MS))
  const url = new URL(path, window.location.origin)
  if (url.pathname === '/api/me') return mockMe as T
  if (url.pathname === '/api/users/access') {
    if (url.searchParams.get('email') === 'missing@example.com') throw new ApiError(404, 'Not found')
    return { user: mockMe, audited_openmetadata_grants: { items: [{ id: 'grant-1', request_id: 'TASK-00001', table_name: 'CUSTOMER_MASTER', table_fully_qualified_name: 'warehouse.customer.CUSTOMER_MASTER', access_type: 'ColumnLevel', access_level: 'Read', columns: ['warehouse.customer.CUSTOMER_MASTER.EMAIL'], granted_at: '2026-10-20T00:00:00Z', expires_at: '2026-12-01T00:00:00Z' }], total: 1 }, associated_database_account: { account_name: 'om::d2719c8a-6c97-4b35-b662-e791647b41b3', state: 'found', account_status: 'OPEN', created_at: '2026-10-20T00:00:00Z' } } as UserAccessAudit as T
  }
  if (url.pathname === '/auth/logout' && init?.method === 'POST') return undefined as T
  if (url.pathname === '/api/tasks') {
    const status = url.searchParams.get('status')
    const type = url.searchParams.get('type')
    const items = mockTasks.filter(task => (!status || task.status === status) && (!type || task.type === type))
    const page: TaskPage = { items, page: 1, page_size: items.length, total: items.length }
    return page as T
  }
  if (url.pathname === '/api/requests') return { items: mockTasks.slice(0, 2), page: 1, page_size: 20, total: 2 } as T
  if (url.pathname === '/api/catalog/tables') return mockCatalog as T
  if (url.pathname === '/api/access-requests' && init?.method === 'POST') return { id: 'req-access-001', request_id: 'TASK-00001', status: 'Open', assignee_count: 1 } as AccessRequestCreated as T
  throw new Error(`No mock registered for ${path}`)
}

const mockCatalog: CatalogPage = { items: [
  { id: 'customer-table', name: 'CUSTOMER_MASTER', fully_qualified_name: 'warehouse.customer.CUSTOMER_MASTER', description: 'Customer profile master data.', service: 'warehouse', database: 'customer', schema_name: 'public', owners: [{ id: 'data-owner-team', type: 'team', display_name: 'Customer Data Owners' }], tags: ['PII.Sensitive'], columns: [{ id: 'customer-id', name: 'CUSTOMER_ID', data_type: 'BIGINT', tags: [] }, { id: 'email', name: 'EMAIL', data_type: 'VARCHAR', tags: ['PII.Sensitive'] }, { id: 'tier', name: 'LOYALTY_TIER', data_type: 'VARCHAR', tags: [] }] },
  { id: 'flight-table', name: 'FLIGHT_OPERATIONS', fully_qualified_name: 'lakehouse.operations.FLIGHT_OPERATIONS', description: 'Operational flight events.', service: 'lakehouse', database: 'operations', schema_name: 'public', owners: [{ id: 'ops-owner-team', type: 'team', display_name: 'Flight Operations Data Owners' }], tags: [], columns: [{ id: 'flight-no', name: 'FLIGHT_NUMBER', data_type: 'VARCHAR', tags: [] }, { id: 'departure', name: 'DEPARTURE_AT', data_type: 'TIMESTAMP', tags: [] }] },
] }
