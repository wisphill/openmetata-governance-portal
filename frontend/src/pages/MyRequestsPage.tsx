import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { Protected } from '../components/Protected'
import { Skeleton } from '../components/Skeleton'
import type { AccessRequestDetail, Task, TaskPage } from '../types/api'

const canCancel = (request: Task) => !['approved', 'cancelled', 'closed', 'rejected'].includes(request.status?.toLocaleLowerCase() ?? '')

export function MyRequestsPage() {
  const { t } = useTranslation('requests')
  const { t: common } = useTranslation('common')
  const [requests, setRequests] = useState<TaskPage>()
  const [error, setError] = useState<'load' | 'cancel' | 'detail'>()
  const [cancellingId, setCancellingId] = useState<string>()
  const [notice, setNotice] = useState<string>()
  const [detail, setDetail] = useState<AccessRequestDetail>()
  const [loadingDetail, setLoadingDetail] = useState(false)
  useEffect(() => { api<TaskPage>('/api/requests').then(setRequests).catch((err: unknown) => { if (!(err instanceof ApiError && err.status === 401)) setError('load') }) }, [])
  const cancel = async (request: Task) => {
    setCancellingId(request.id); setError(undefined); setNotice(undefined)
    try {
      await api<void>(`/api/requests/${encodeURIComponent(request.id)}`, { method: 'DELETE' })
      setRequests(current => current ? { ...current, items: current.items.map(item => item.id === request.id ? { ...item, status: 'Closed' } : item) } : current)
      setNotice(t('cancelled'))
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setError('cancel')
    } finally { setCancellingId(undefined) }
  }
  const view = async (request: Task) => {
    setLoadingDetail(true); setError(undefined)
    try { setDetail(await api<AccessRequestDetail>(`/api/requests/${encodeURIComponent(request.id)}`)) }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) setError('detail') }
    finally { setLoadingDetail(false) }
  }
  const formatDate = (value?: string) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
  return <Protected><section className="page">
    <div className="page-header"><div><p className="eyebrow">{common('source')}</p><h1>{common('myRequests')}</h1><p>{t('description')}</p></div><Link className="button-primary page-action create-request-button" to="/requests/new"><span aria-hidden="true">+</span>{common('createRequest')}</Link></div>
    {error && <p className="alert" role="alert">{error === 'cancel' ? t('cancelFailed') : error === 'detail' ? t('detailFailed') : common('requestFailed')}</p>}
    {notice && <p className="success" role="status">{notice}</p>}
    {!requests && !error && <Skeleton className="skeleton--line" />}
    {requests && !requests.items.length && <div className="empty-state"><p>{t('empty')}</p><Link to="/requests/new">{t('createFirst')}</Link></div>}
    {requests && requests.items.length > 0 && <><div className="table-wrap request-table-wrap"><table><thead><tr><th>{t('id')}</th><th>{t('type')}</th><th>{t('reason')}</th><th>{t('assignees')}</th><th>{t('status')}</th><th>{t('requestedAt')}</th><th className="request-actions-heading">{t('actions')}</th></tr></thead><tbody>{requests.items.map(request => <tr key={request.id}><td><code className="pill">{request.request_id ?? request.id}</code></td><td>{request.type ?? '—'}</td><td className="request-reason">{request.reason ?? '—'}</td><td className="request-assignees">{request.assignees?.length ? request.assignees.join(', ') : t('notAssigned')}</td><td>{request.status ?? '—'}</td><td>{formatDate(request.created_at)}</td><td className="request-actions"><button className="button-secondary" disabled={loadingDetail} onClick={() => void view(request)}>{t('view')}</button>{canCancel(request) && <button className="button-danger" disabled={cancellingId === request.id} onClick={() => void cancel(request)}>{cancellingId === request.id ? t('cancelling') : t('cancel')}</button>}</td></tr>)}</tbody></table></div><ul className="request-cards">{requests.items.map(request => <li key={request.id}><article className="request-card"><div className="request-card__top"><code className="pill">{request.request_id ?? request.id}</code><span>{request.status ?? '—'}</span></div><div className="request-card__detail"><span>{t('type')}</span><strong>{request.type ?? '—'}</strong></div><div className="request-card__detail"><span>{t('assignees')}</span><strong>{request.assignees?.length ? request.assignees.join(', ') : t('notAssigned')}</strong></div><div className="request-card__detail"><span>{t('reason')}</span><strong>{request.reason ?? '—'}</strong></div><div className="request-card__actions"><button className="button-secondary" disabled={loadingDetail} onClick={() => void view(request)}>{t('view')}</button>{canCancel(request) && <button className="button-danger" disabled={cancellingId === request.id} onClick={() => void cancel(request)}>{cancellingId === request.id ? t('cancelling') : t('cancel')}</button>}</div></article></li>)}</ul></>}
    {detail && <div className="request-modal-backdrop" role="presentation"><section className="request-modal" role="dialog" aria-modal="true" aria-labelledby="request-details-title"><div className="request-modal__header"><div><p className="eyebrow">{detail.request_id ?? detail.id}</p><h2 id="request-details-title">{t('requestDetails')}</h2></div><button className="button-secondary" onClick={() => setDetail(undefined)}>{t('closeDetails')}</button></div><dl className="request-detail-grid"><div><dt>{t('table')}</dt><dd><strong>{detail.table_name ?? '—'}</strong><code>{detail.table_fully_qualified_name ?? '—'}</code></dd></div><div><dt>{t('database')}</dt><dd>{detail.database ?? '—'}</dd></div><div><dt>{t('schema')}</dt><dd>{detail.schema_name ?? '—'}</dd></div><div><dt>{t('accessLevel')}</dt><dd>{detail.access_level ?? '—'}</dd></div><div><dt>{t('accessType')}</dt><dd>{detail.access_type ?? '—'}</dd></div><div><dt>{t('columns')}</dt><dd>{detail.columns.length ? detail.columns.join(', ') : t('allColumns')}</dd></div><div><dt>{t('assignees')}</dt><dd>{detail.assignees?.length ? detail.assignees.join(', ') : t('notAssigned')}</dd></div><div><dt>{t('status')}</dt><dd>{detail.status ?? '—'}</dd></div><div><dt>{t('requestedAt')}</dt><dd>{formatDate(detail.created_at?.toString())}</dd></div><div><dt>{t('expiresAt')}</dt><dd>{formatDate(detail.expires_at)}</dd></div><div className="request-detail-grid__wide"><dt>{t('reason')}</dt><dd>{detail.reason ?? '—'}</dd></div></dl></section></div>}
  </section></Protected>
}
