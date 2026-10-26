import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { Protected } from '../components/Protected'
import { Skeleton } from '../components/Skeleton'
import type { TaskPage } from '../types/api'

export function MyRequestsPage() {
  const { t } = useTranslation('requests')
  const { t: common } = useTranslation('common')
  const [requests, setRequests] = useState<TaskPage>()
  const [error, setError] = useState(false)
  useEffect(() => { api<TaskPage>('/api/requests').then(setRequests).catch((err: unknown) => { if (!(err instanceof ApiError && err.status === 401)) setError(true) }) }, [])
  return <Protected><section className="page">
    <div className="page-header"><div><p className="eyebrow">{common('source')}</p><h1>{common('myRequests')}</h1><p>{t('description')}</p></div><Link className="button-primary page-action" to="/requests/new">{common('createRequest')}</Link></div>
    {error && <p className="alert" role="alert">{common('requestFailed')}</p>}
    {!requests && !error && <Skeleton className="skeleton--line" />}
    {requests && !requests.items.length && <div className="empty-state"><p>{t('empty')}</p><Link to="/requests/new">{t('createFirst')}</Link></div>}
    {requests && requests.items.length > 0 && <div className="table-wrap"><table><thead><tr><th>{t('id')}</th><th>{t('type')}</th><th>{t('reason')}</th><th>{t('status')}</th><th>{t('requestedAt')}</th></tr></thead><tbody>{requests.items.map(request => <tr key={request.id}><td><code className="pill">{request.request_id ?? request.id}</code></td><td>{request.type ?? '—'}</td><td className="request-reason">{request.reason ?? '—'}</td><td>{request.status ?? '—'}</td><td>{request.created_at ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(request.created_at)) : '—'}</td></tr>)}</tbody></table></div>}
  </section></Protected>
}
