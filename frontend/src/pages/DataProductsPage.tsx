import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../api/client'
import { Protected } from '../components/Protected'
import type { CatalogPage, CatalogTable, DataProductPublicationCreate, DataProductPublicationCreated, TaskPage } from '../types/api'

export function DataProductsPage() {
  const [candidates, setCandidates] = useState<CatalogPage>()
  const [products, setProducts] = useState<TaskPage>()
  const [selected, setSelected] = useState<CatalogTable>()
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState<string>()
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')

  const load = async () => {
    const [views, published] = await Promise.allSettled([api<CatalogPage>('/api/data-product-publications/candidates'), api<TaskPage>('/api/data-products')])
    if (views.status === 'fulfilled') setCandidates(views.value)
    if (published.status === 'fulfilled') setProducts(published.value)
    const failure = [views, published].find((result): result is PromiseRejectedResult => result.status === 'rejected')
    if (failure && !(failure.reason instanceof ApiError && failure.reason.status === 401)) setError(failure.reason instanceof ApiError ? failure.reason.message : 'Không thể tải Data Product.')
  }
  useEffect(() => { void load() }, [])
  const filtered = useMemo(() => (candidates?.items ?? []).filter(view => `${view.name} ${view.fully_qualified_name ?? ''}`.toLowerCase().includes(query.toLowerCase())), [candidates, query])
  const submit = async () => {
    if (!selected) return
    setBusy(true); setError(undefined); setNotice(undefined)
    try {
      const result = await api<DataProductPublicationCreated>('/api/data-product-publications', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ table_id: selected.id, reason } satisfies DataProductPublicationCreate) })
      setNotice(`Đã gửi yêu cầu ${result.request_id} tới reviewer.`); setSelected(undefined); setReason(''); await load()
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Không thể tạo yêu cầu.') }
    finally { setBusy(false) }
  }
  return <Protected><section className="page page--catalog">
    <div className="page-header"><div><p className="eyebrow">Source: OpenMetadata</p><h1>Data Products</h1><p>Publish an unpublished security View as a Data Product, then manage its lifecycle in OpenMetadata.</p></div></div>
    {notice && <p className="success" role="status">{notice}</p>}{error && <p className="alert" role="alert">{error}</p>}
    <div className="catalog-layout"><section className="card catalog-list"><label className="field-label" htmlFor="product-view-search">Views available for publication</label><input id="product-view-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search Views" />
      {!candidates && <p className="empty-value">Loading…</p>}<ul className="catalog-items">{filtered.map(view => <li key={view.id}><button className={selected?.id === view.id ? 'catalog-item catalog-item--selected' : 'catalog-item'} onClick={() => { setSelected(view); setError(undefined) }}><strong>{view.name}</strong><span>{view.fully_qualified_name ?? view.schema_name ?? '—'}</span><small>{view.owners.map(owner => owner.display_name ?? owner.name ?? owner.id).join(', ') || 'No data owner'}</small></button></li>)}</ul>
      {candidates && !filtered.length && <p className="empty-state">No unpublished Views are available.</p>}</section>
      <section className="card request-form">{!selected ? <p className="empty-state">Select a View to submit a Data Product publication request.</p> : <><h2>{selected.name}</h2><p className="catalog-fqn">{selected.fully_qualified_name}</p><p className="owner-line">Reviewers: {selected.owners.map(owner => owner.display_name ?? owner.name ?? owner.id).join(', ') || 'No data owner'}</p><label className="field-label">Publication reason<textarea value={reason} minLength={3} maxLength={2000} onChange={event => setReason(event.target.value)} placeholder="Describe consumers and intended use." /></label><button className="button-primary" disabled={busy || reason.trim().length < 3 || !selected.owners.length} onClick={() => void submit()}>{busy ? 'Submitting…' : 'Submit publication request'}</button></>}</section></div>
    <section className="access-grants"><h2>Data Product publications</h2><p>Approved tag-update requests form the current Data Product register. To revoke, submit a Tag Update request to remove the published tag.</p>{!products && <p className="empty-value">Loading…</p>}{products && !products.items.length && <p className="empty-state">No Data Product publication requests yet.</p>}{products && Boolean(products.items.length) && <div className="table-wrap"><table><thead><tr><th>View</th><th>Request</th><th>Status</th><th>Reason</th></tr></thead><tbody>{products.items.map(product => <tr key={product.id}><td><strong>{product.entity?.displayName as string ?? product.entity?.name as string ?? '—'}</strong></td><td>{product.request_id ?? product.id}</td><td>{product.status ?? '—'}</td><td>{product.reason ?? '—'}</td></tr>)}</tbody></table></div>}</section>
  </section></Protected>
}
