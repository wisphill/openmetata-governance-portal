export type Me = { identity: { id: string; username: string; display_name?: string; email?: string; title?: string }; teams: Array<Record<string, unknown>>; roles: { direct: Array<Record<string, unknown>>; inherited: Array<Record<string, unknown>> }; policies: Array<Record<string, unknown>>; is_admin: boolean; source: 'openmetadata' }
export type Classification = 'C1' | 'C2' | 'C3' | 'C4'
export type Task = { id: string; code?: string; title?: string; process?: { code: string; name: string }; classification?: Classification; type?: string; status?: string; assignee?: string; entity?: { name?: string; [key: string]: unknown }; created_at?: string; due_at?: string; requester?: string; link?: string }
export type TaskPage = { items: Task[]; page: number; page_size: number; total?: number }
