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
const taskCode = (task: Task) => task.code ?? task.request_id ?? task.id.slice(0, 8)
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
  const [handling, setHandling] = useState<Task>()
  const [resolution, setResolution] = useState<'Approved' | 'Rejected'>('Approved')
  const [comment, setComment] = useState('')
  const [resolving, setResolving] = useState(false)
  const [resolutionError, setResolutionError] = useState<string>()
  const [resolutionFeedback, setResolutionFeedback] = useState<{ kind: 'success' | 'error', message: string }>()

  const loadTasks = async (showError = true) => {
    if (showError) setError(false)
    try {
      setTasks(await api<TaskPage>('/api/tasks'))
    } catch (err) {
      if (showError && !(err instanceof ApiError && err.status === 401)) setError(true)
    }
  }

  useEffect(() => {
    void loadTasks()
  }, [])

  const items = tasks?.items ?? []
  const filters = useMemo<Filter[]>(() => {
    const processCodes = [...new Set(items.map(task => task.process?.code).filter((code): code is string => Boolean(code)))].sort() as Filter[]
    return ['all', 'overdue', 'C4', ...processCodes]
  }, [items])
  const visible = items.filter(task => matches(task, filter))
  const total = tasks?.total ?? items.length

  const toggle = (id: string) => setSelected(current => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next })
  const openHandler = (task: Task) => { setHandling(task); setResolution('Approved'); setComment(''); setResolutionError(undefined); setResolutionFeedback(undefined) }
  const resolutionFailureMessage = (err: unknown) => {
    if (!(err instanceof ApiError)) return t('resolutionFailed')
    if (err.status === 403) return t('resolutionNotAllowed')
    if (err.status === 409) return t('resolutionNoLongerAvailable')
    if (err.status === 504) return t('resolutionTimedOut')
    return err.message && err.message !== 'requestFailed'
      ? t('resolutionFailedWithReason', { reason: err.message })
      : t('resolutionFailed')
  }
  const resolveTask = async () => {
    if (!handling) return
    const code = taskCode(handling)
    const decision = resolution
    setResolving(true); setResolutionError(undefined); setResolutionFeedback(undefined)
    try {
      const resolved = await api<Task>(`/api/tasks/${encodeURIComponent(handling.id)}/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ resolution_type: resolution, comment }) })
      setTasks(current => current ? { ...current, items: current.items.map(task => task.id === resolved.id ? { ...task, ...resolved } : task) } : current)
      setHandling(undefined)
      setResolutionFeedback({ kind: 'success', message: t(decision === 'Approved' ? 'decisionApproved' : 'decisionRejected', { code }) })
      void loadTasks(false)
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        const message = resolutionFailureMessage(err)
        setResolutionError(message)
        setResolutionFeedback({ kind: 'error', message })
      }
    }
    finally { setResolving(false) }
  }
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

    {resolutionFeedback && <p className={resolutionFeedback.kind === 'success' ? 'success' : 'alert'} role={resolutionFeedback.kind === 'success' ? 'status' : 'alert'}>{resolutionFeedback.message}</p>}
    {error && <p className="alert" role="alert">{t('requestFailed', { ns: 'common' })}</p>}
    {!tasks && !error && <TaskTableSkeleton />}
    {tasks && visible.length === 0 && <p className="empty-state">{items.length ? t('noMatches') : t('empty', { ns: 'common' })}</p>}

    {visible.length > 0 && <>
      <div className="table-wrap task-table-wrap">
        <table className="task-table">
          <thead><tr><th className="col-check"><span className="sr-only">{t('select')}</span></th><th>{t('code')}</th><th>{t('task')}</th><th>{t('entity')}</th><th>{t('reason')}</th><th>{t('level')}</th><th>{t('requester')}</th><th>{t('due')}</th><th><span className="sr-only">{t('actions')}</span></th></tr></thead>
          <tbody>{visible.map(task => {
            const code = taskCode(task)
            return <tr key={task.id} className={selected.has(task.id) ? 'is-selected' : undefined}>
              <td className="col-check"><input type="checkbox" checked={selected.has(task.id)} onChange={() => toggle(task.id)} aria-label={t('selectTask', { code })} /></td>
              <td><code className="pill">{code}</code></td>
              <td className="col-task"><strong>{taskTitle(task, t('unknown'))}</strong>{task.process && <small>{task.process.code} · {task.process.name}</small>}</td>
              <td>{task.entity?.name ? <code className="pill pill--entity">{task.entity.name}</code> : '—'}</td>
              <td className="task-reason">{task.reason ?? '—'}</td>
              <td><Level value={task.classification} /></td>
              <td><Requester name={task.requester} /></td>
              <td><DueLabel value={task.due_at} /></td>
              <td className="col-action"><button className="button-secondary" onClick={() => openHandler(task)}>{t('process')}</button></td>
            </tr>
          })}</tbody>
        </table>
      </div>

      <ul className="task-cards">{visible.map(task => <li key={task.id} className="task-card">
        <div className="task-card__top"><code className="pill">{taskCode(task)}</code><span className="task-status">{task.status ?? '—'}</span></div>
        <strong className="task-card__title">{taskTitle(task, t('unknown'))}</strong>
        <dl className="task-card__details">
          <div><dt>{t('type')}</dt><dd>{task.type ?? '—'}</dd></div>
          <div><dt>{t('entity')}</dt><dd>{task.entity?.name ?? '—'}</dd></div>
          <div><dt>{t('requester')}</dt><dd>{task.requester ?? '—'}</dd></div>
          <div><dt>{t('assignees')}</dt><dd>{task.assignees?.length ? task.assignees.join(', ') : '—'}</dd></div>
          <div className="task-card__detail-wide"><dt>{t('reason')}</dt><dd>{task.reason ?? '—'}</dd></div>
          <div><dt>{t('created')}</dt><dd>{task.created_at ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(task.created_at)) : '—'}</dd></div>
        </dl>
        <DueLabel value={task.due_at} />
        <button className="button-secondary" onClick={() => openHandler(task)}>{t('process')}</button>
      </li>)}</ul>
    </>}
    {handling && <div className="task-modal-backdrop" role="presentation"><section className="task-modal" role="dialog" aria-modal="true" aria-labelledby="handle-task-title"><div className="task-modal__header"><div><p className="eyebrow">{taskCode(handling)}</p><h2 id="handle-task-title">{t('handleTask', { code: taskCode(handling) })}</h2></div><button className="button-secondary" onClick={() => setHandling(undefined)}>{t('close')}</button></div><p className="task-modal__summary">{handling.type ?? t('unknown')} · {handling.entity?.name ?? '—'}</p><div className="resolution-options"><label><input type="radio" name="resolution" checked={resolution === 'Approved'} onChange={() => setResolution('Approved')} />{t('approve')}</label><label><input type="radio" name="resolution" checked={resolution === 'Rejected'} onChange={() => setResolution('Rejected')} />{t('reject')}</label></div><label className="field-label">{t('resolutionComment')}<textarea value={comment} minLength={1} maxLength={2000} onChange={event => setComment(event.target.value)} placeholder={t('resolutionCommentPlaceholder')} /></label>{resolutionError && <p className="alert" role="alert">{resolutionError}</p>}<button className={resolution === 'Approved' ? 'button-primary' : 'button-danger'} disabled={resolving || !comment.trim()} onClick={() => void resolveTask()}>{resolving ? t('submittingDecision') : t('submitDecision')}</button></section></div>}
  </section></Protected>
}
