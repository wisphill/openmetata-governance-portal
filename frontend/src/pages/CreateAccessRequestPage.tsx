import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError } from '../api/client'
import { Protected } from '../components/Protected'
import { Link } from 'react-router-dom'
import type { AccessRequestCreate, AccessRequestCreated, CatalogPage, CatalogTable } from '../types/api'

export function CreateAccessRequestPage() {
  const { t } = useTranslation('common')
  const [page, setPage] = useState<CatalogPage>()
  const [selected, setSelected] = useState<CatalogTable>()
  const [columns, setColumns] = useState<Set<string>>(new Set())
  const [access, setAccess] = useState<'READ' | 'WRITE'>('READ')
  const [reason, setReason] = useState('')
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string>()
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState<AccessRequestCreated>()

  useEffect(() => { api<CatalogPage>('/api/catalog/tables').then(setPage).catch((err: unknown) => setError(err instanceof ApiError ? err.message : 'requestFailed')) }, [])
  const tables = useMemo(() => (page?.items ?? []).filter(table => `${table.name} ${table.fully_qualified_name ?? ''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())), [page, query])
  const choose = (table: CatalogTable) => { setSelected(table); setColumns(new Set()); setSuccess(undefined); setError(undefined) }
  const toggleColumn = (id: string) => setColumns(current => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const loadMore = async () => {
    if (!page?.after) return
    try {
      const next = await api<CatalogPage>(`/api/catalog/tables?after=${encodeURIComponent(page.after)}`)
      setPage(current => current ? { items: [...current.items, ...next.items], after: next.after } : next)
    } catch (err) { setError(err instanceof ApiError ? err.message : 'requestFailed') }
  }
  const submit = async () => {
    if (!selected) return
    setSubmitting(true); setError(undefined); setSuccess(undefined)
    const payload: AccessRequestCreate = { table_id: selected.id, column_ids: [...columns], access, reason }
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 15_000)
    try { setSuccess(await api<AccessRequestCreated>('/api/access-requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: controller.signal })) }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) setError(err instanceof ApiError ? err.message : 'requestFailed') }
    finally { window.clearTimeout(timeout); setSubmitting(false) }
  }

  return <Protected><section className="page page--catalog">
    <div className="page-header"><div><p className="eyebrow">{t('source')}</p><h1>{t('createRequest')}</h1><p>{t('createRequestDescription')}</p></div></div>
    {error && <p className="alert" role="alert">{t('accessRequestFailed')} {error !== 'requestFailed' && `(${error})`}</p>}
    {success && <p className="success" role="status">{t('accessRequestCreated', { count: success.assignee_count, id: success.request_id })} <Link to="/requests">{t('myRequests')}</Link></p>}
    <div className="catalog-layout">
      <section className="card catalog-list"><label className="field-label" htmlFor="table-search">{t('browseProperties')}</label><input id="table-search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('searchProperties')} />
        {!page && !error && <p className="empty-value">{t('loading')}</p>}
        {page && <ul className="catalog-items">{tables.map(table => <li key={table.id}><button className={selected?.id === table.id ? 'catalog-item catalog-item--selected' : 'catalog-item'} onClick={() => choose(table)}><strong>{table.name}</strong><span>{table.fully_qualified_name ?? table.schema_name ?? '—'}</span><small>{t('columnsCount', { count: table.columns.length })}</small></button></li>)}</ul>}
        {page?.after && <button className="button-secondary catalog-more" onClick={() => void loadMore()}>{t('morePropertiesAvailable')}</button>}
      </section>
      <section className="card request-form">
        {!selected ? <p className="empty-state">{t('selectProperty')}</p> : <>
          <h2>{selected.name}</h2><p className="catalog-fqn">{selected.fully_qualified_name}</p>
          {selected.description && <p>{selected.description}</p>}
          <p className="owner-line">{t('dataOwners')}: {selected.owners.map(owner => owner.display_name ?? owner.name ?? owner.id).join(', ') || t('noDataOwner')}</p>
          <fieldset><legend>{t('requestedColumns')}</legend><p className="field-help">{t('allColumnsHint')}</p><div className="column-list">{selected.columns.map(column => <label key={column.id}><input type="checkbox" checked={columns.has(column.id)} onChange={() => toggleColumn(column.id)} /><span><strong>{column.name}</strong>{column.data_type && <small>{column.data_type}</small>}</span></label>)}</div></fieldset>
          <label className="field-label">{t('accessLevel')}<select value={access} onChange={event => setAccess(event.target.value as 'READ' | 'WRITE')}><option value="READ">{t('read')}</option><option value="WRITE">{t('write')}</option></select></label>
          <label className="field-label">{t('requestReason')}<textarea value={reason} minLength={3} maxLength={2000} onChange={event => setReason(event.target.value)} placeholder={t('requestReasonPlaceholder')} /></label>
          <button className="button-primary" disabled={submitting || reason.trim().length < 3 || !selected.owners.length} onClick={() => void submit()}>{submitting ? t('submitting') : t('submitAccessRequest')}</button>
        </>}
      </section>
    </div>
  </section></Protected>
}
