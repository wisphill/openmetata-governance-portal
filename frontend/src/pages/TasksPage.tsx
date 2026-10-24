import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { Icon } from '../components/Layout'
import { Protected } from '../components/Protected'
import { Skeleton } from '../components/Skeleton'
import type { Task, TaskPage } from '../types/api'
import { dueState, initials } from '../utils/format'

type Filter = 'all' | 'overdue' | 'C4' | `P${string}`

const isOverdue = (task: Task) => Boolean(task.due_at) && dueState(task.due_at!).kind === 'overdue'
const taskCode = (task: Task) => task.code ?? task.id.slice(0, 8)
const taskTitle = (task: Task, fallback: string) => task.title ?? task.type ?? fallback

function matches(task: Task, filter: Filter) {
  if (filter === 'all') return true
  if (filter === 'overdue') return isOverdue(task)
  if (filter === 'C4') return task.classification === 'C4'
  return task.process?.code === filter
}

const shortDate = (date: Date, language: string) => language.startsWith('vi')
  ? `${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}`
  : new Intl.DateTimeFormat(language, { month: 'short', day: 'numeric' }).format(date)

function DueLabel({ value }: { value?: string }) {
  const { t, i18n } = useTranslation('tasks')
  if (!value) return <span className="due due--neutral">—</span>
  const state = dueState(value)
  const label = state.kind === 'overdue' ? t('overdueBy', { count: state.count })
    : state.kind === 'today' ? t('dueToday')
    : state.kind === 'businessDaysLeft' ? t('businessDaysLeft', { count: state.count })
    : t('dueOn', { date: shortDate(state.date, i18n.language) })
  return <span className={`due due--${state.tone}`}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></svg>{label}</span>
}

function Level({ value }: { value?: Task['classification'] }) {
  return value ? <span className={`level level--${value.toLowerCase()}`}>{value}</span> : <span className="empty-value">—</span>
}

function Requester({ name }: { name?: string }) {
  if (!name) return <span className="empty-value">—</span>
  return <span className="requester"><span className="avatar avatar--sm" aria-hidden="true">{initials(name)}</span><span>{name}</span></span>
}

function openTask(task: Task) { if (task.link) window.open(task.link, '_blank', 'noopener,noreferrer') }

function TaskTableSkeleton() {
  return <div className="table-wrap" aria-busy="true"><table className="task-table"><tbody>{Array.from({ length: 5 }, (_, row) => <tr key={row}><td className="col-check"><Skeleton className="skeleton--check" /></td>{Array.from({ length: 6 }, (_, column) => <td key={column}><Skeleton className="skeleton--cell" /></td>)}</tr>)}</tbody></table></div>
}

export function TasksPage() {
  const { t } = useTranslation('tasks')
  const { me } = useAuth()
  const [tasks, setTasks] = useState<TaskPage>()
  const [error, setError] = useState(false)
  const [filter, setFilter] = useState<Filter>('all')
  const [selected, setSelected] = useState<Set<string>>(new Set())

  useEffect(() => {
    setError(false)
    api<TaskPage>('/api/tasks').then(setTasks).catch((err: unknown) => { if (!(err instanceof ApiError && err.status === 401)) setError(true) })
  }, [])

  const items = tasks?.items ?? []
  const filters = useMemo<Filter[]>(() => {
    const processCodes = [...new Set(items.map(task => task.process?.code).filter((code): code is string => Boolean(code)))].sort() as Filter[]
    return ['all', 'overdue', 'C4', ...processCodes]
  }, [items])
  const visible = items.filter(task => matches(task, filter))
  const total = tasks?.total ?? items.length

  const toggle = (id: string) => setSelected(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next })
  const name = me?.identity.display_name ?? me?.identity.username
  const role = me?.roles.direct[0]
  const roleName = role ? String(role.displayName ?? role.name ?? '') : ''
  const subtitle = [t('greeting', { name }), me?.identity.title, roleName].filter(Boolean).join(' · ')
  const chipLabel = (value: Filter) => value === 'all' ? t('all') : value === 'overdue' ? t('overdue') : value

  return <Protected><section className="page page--tasks">
    <div className="page-header"><div><h1>{t('title')}</h1><p>{subtitle}</p></div></div>

    <div className="tabs" role="tablist">
      <button className="tab tab--active" role="tab" aria-selected="true">{t('assignedToMe')}{tasks && <span className="count-badge">{total}</span>}</button>
    </div>

    {tasks && <div className="chips" role="group" aria-label={t('filter')}>
      {filters.map(value => <button key={value} className={`chip${filter === value ? ' chip--active' : ''}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>{chipLabel(value)}</button>)}
    </div>}

    {selected.size > 0 && <div className="selection-bar" role="status">
      <span>{t('selected', { count: selected.size })}</span>
      <button className="link-button" onClick={() => setSelected(new Set())}>{t('clearSelection')}</button>
    </div>}

    {error && <p className="alert" role="alert">{t('requestFailed', { ns: 'common' })}</p>}
    {!tasks && !error && <TaskTableSkeleton />}
    {tasks && visible.length === 0 && <p className="empty-state">{items.length ? t('noMatches') : t('empty', { ns: 'common' })}</p>}

    {visible.length > 0 && <>
      <div className="table-wrap task-table-wrap">
        <table className="task-table">
          <thead><tr><th className="col-check"><span className="sr-only">{t('select')}</span></th><th>{t('code')}</th><th>{t('task')}</th><th>{t('entity')}</th><th>{t('level')}</th><th>{t('requester')}</th><th>{t('due')}</th><th><span className="sr-only">{t('actions')}</span></th></tr></thead>
          <tbody>{visible.map(task => {
            const code = taskCode(task)
            return <tr key={task.id} className={selected.has(task.id) ? 'is-selected' : undefined}>
              <td className="col-check"><input type="checkbox" checked={selected.has(task.id)} onChange={() => toggle(task.id)} aria-label={t('selectTask', { code })} /></td>
              <td><code className="pill">{code}</code></td>
              <td className="col-task"><strong>{taskTitle(task, t('unknown'))}</strong>{task.process && <small>{task.process.code} · {task.process.name}</small>}</td>
              <td>{task.entity?.name ? <code className="pill pill--entity">{task.entity.name}</code> : '—'}</td>
              <td><Level value={task.classification} /></td>
              <td><Requester name={task.requester} /></td>
              <td><DueLabel value={task.due_at} /></td>
              <td className="col-action"><button className="button-secondary" onClick={() => openTask(task)}>{t('process')}</button></td>
            </tr>
          })}</tbody>
        </table>
      </div>

      <ul className="task-cards">{visible.map(task => <li key={task.id} className="task-card">
        <div className="task-card__top"><code className="pill">{taskCode(task)}</code><Level value={task.classification} /></div>
        <strong className="task-card__title">{taskTitle(task, t('unknown'))}</strong>
        <p className="task-card__meta">{[task.requester, task.entity?.name].filter(Boolean).join(' · ')}</p>
        <DueLabel value={task.due_at} />
      </li>)}</ul>
    </>}
  </section></Protected>
}
