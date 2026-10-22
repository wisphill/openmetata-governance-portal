import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api/client'
import { Protected } from '../components/Protected'
import type { TaskPage } from '../types/api'

export function TasksPage() {
  const { t, i18n } = useTranslation('tasks'); const [tasks, setTasks] = useState<TaskPage>(); const [error, setError] = useState(false); const [status, setStatus] = useState(''); const [type, setType] = useState('')
  useEffect(() => { const params = new URLSearchParams(); if (status) params.set('status', status); if (type) params.set('type', type); setError(false); api<TaskPage>(`/api/tasks?${params}`).then(setTasks).catch((err: unknown) => { if (!(err instanceof ApiError && err.status === 401)) setError(true) }) }, [status, type])
  const format = (value?: string) => value ? new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' }).format(new Date(value)) : '—'
  return <Protected><section><h1>{t('title')}</h1><div className="filters"><select value={status} onChange={e => setStatus(e.target.value)}><option value="">{t('allStatuses')}</option><option value="Open">Open</option><option value="InProgress">In progress</option></select><select value={type} onChange={e => setType(e.target.value)}><option value="">{t('allTypes')}</option><option value="Request">Request</option><option value="Approval">Approval</option></select></div>{error && <p role="alert">{t('requestFailed', { ns: 'common' })}</p>}{!tasks && !error && <p>{t('loading', { ns: 'common' })}</p>}{tasks?.items.length === 0 && <p>{t('empty', { ns: 'common' })}</p>}{tasks && tasks.items.length > 0 && <div className="table-wrap"><table><thead><tr>{['type','status','entity','created','due','requester'].map(key => <th key={key}>{t(key)}</th>)}</tr></thead><tbody>{tasks.items.map(task => <tr key={task.id}><td>{task.type ?? t('unknown')}</td><td><span className="badge">{task.status ?? t('unknown')}</span></td><td>{task.link ? <a href={task.link} target="_blank" rel="noreferrer">{task.entity?.name ?? task.id}</a> : task.entity?.name ?? '—'}</td><td>{format(task.created_at)}</td><td>{format(task.due_at)}</td><td>{task.requester ?? '—'}</td></tr>)}</tbody></table></div>}</section></Protected>
}
