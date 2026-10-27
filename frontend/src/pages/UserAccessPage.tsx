import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, api } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { Protected } from '../components/Protected'
import type { AccessRevocation, GrantedAccess, UserAccessAudit } from '../types/api'

function Names({ values }: { values: Array<Record<string, unknown>> }) {
  return values.length
    ? <ul className="item-list">{values.map((value, index) => <li key={String(value.id ?? index)}>{String(value.displayName ?? value.name ?? value.id ?? '')}</li>)}</ul>
    : <p className="empty-value">—</p>
}

function TemporaryAccessTable({ grants, canRevoke, revokingGrantId, onRevoke }: { grants: GrantedAccess[]; canRevoke: boolean; revokingGrantId?: string; onRevoke: (grant: GrantedAccess) => void }) {
  const { t } = useTranslation('common')
  const { t: auditT } = useTranslation('accessAudit')
  const date = (value?: string) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value)) : '—'
  return <div className="table-wrap"><table><thead><tr><th>{t('auditRecord')}</th><th>{t('resource')}</th><th>{t('scope')}</th><th>{t('accessLevel')}</th><th>{t('columns')}</th><th>{t('grantedAt')}</th><th>{t('expires')}</th>{canRevoke && <th>{auditT('actions')}</th>}</tr></thead><tbody>
    {grants.map(grant => <tr key={grant.id}><td><strong>{grant.id}</strong><small>{grant.request_id ?? '—'}</small></td><td><strong>{grant.table_name}</strong><small>{grant.table_fully_qualified_name}</small></td><td>{grant.access_type}</td><td>{grant.access_level}</td><td>{grant.columns.length ? grant.columns.join(', ') : '—'}</td><td>{date(grant.granted_at)}</td><td>{date(grant.expires_at)}</td>{canRevoke && <td><button className="button-danger" type="button" disabled={revokingGrantId === grant.id} onClick={() => onRevoke(grant)}>{revokingGrantId === grant.id ? auditT('revoking') : auditT('revoke')}</button></td>}</tr>)}
  </tbody></table></div>
}

function DatabaseAccount({ associated_database_account: account }: Pick<UserAccessAudit, 'associated_database_account'>) {
  const { t } = useTranslation('common')
  const date = account.created_at ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(account.created_at)) : '—'
  const stateLabel = t(`databaseAccountStates.${account.state}`)
  return <section className="access-grants"><h2>{t('associatedDatabaseAccount')}</h2><p>{t('associatedDatabaseAccountDescription')}</p><div className="table-wrap"><table><thead><tr><th>{t('account')}</th><th>{t('databaseCheck')}</th><th>{t('accountStatus')}</th><th>{t('createdAt')}</th></tr></thead><tbody><tr><td><strong>{account.account_name}</strong></td><td>{stateLabel}</td><td>{account.account_status ?? '—'}</td><td>{date}</td></tr></tbody></table></div></section>
}

export function UserAccessPage() {
  const { t } = useTranslation('common')
  const { t: auditT } = useTranslation('accessAudit')
  const { me } = useAuth()
  const [email, setEmail] = useState('')
  const [result, setResult] = useState<UserAccessAudit>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [revokingGrantId, setRevokingGrantId] = useState<string>()

  async function search(event: FormEvent) {
    event.preventDefault()
    const normalizedEmail = email.trim()
    if (!normalizedEmail) return
    setLoading(true)
    setError(undefined)
    try {
      setResult(await api<UserAccessAudit>(`/api/users/access?email=${encodeURIComponent(normalizedEmail)}`))
    } catch (cause) {
      setResult(undefined)
      setError(cause instanceof ApiError && cause.status === 404 ? t('userNotFound') : t('requestFailed'))
    } finally {
      setLoading(false)
    }
  }

  async function revoke(grant: GrantedAccess) {
    if (!result) return
    setRevokingGrantId(grant.id)
    setError(undefined)
    try {
      await api<AccessRevocation>(`/api/users/access/${encodeURIComponent(result.user.identity.id)}/grants/${encodeURIComponent(grant.id)}/revoke`, { method: 'POST' })
      setResult(current => current ? { ...current, audited_openmetadata_grants: { ...current.audited_openmetadata_grants, items: current.audited_openmetadata_grants.items.filter(item => item.id !== grant.id), total: Math.max(0, current.audited_openmetadata_grants.total - 1) } } : current)
    } catch {
      setError(auditT('revokeFailed'))
    } finally {
      setRevokingGrantId(undefined)
    }
  }

  const user = result?.user
  const grants = result?.audited_openmetadata_grants.items ?? []
  return <Protected><section className="page"><div className="page-header"><div><p className="eyebrow">{t('source')}</p><h1>{t('userAccess')}</h1><p>{t('userAccessDescription')}</p></div></div>
    <form className="user-access-search" onSubmit={search}>
      <label className="field-label" htmlFor="user-email">{t('emailAddress')}<input id="user-email" type="email" value={email} onChange={event => setEmail(event.target.value)} required autoComplete="email" /></label>
      <button className="button-primary" type="submit" disabled={loading}>{loading ? t('loading') : t('searchUserAccess')}</button>
    </form>
    {error && <p className="notice notice--error" role="alert">{error}</p>}
    {user && <>
      <section className="access-audit-user"><h2>{user.identity.display_name ?? user.identity.username}</h2><p>{user.identity.email ?? user.identity.username}</p></section>
      <div className="card-grid card-grid--two"><article className="card"><h2>{t('teams')}</h2><Names values={user.teams} /></article><article className="card"><h2>{t('directRoles')}</h2><Names values={user.roles.direct} /></article><article className="card"><h2>{t('inheritedRoles')}</h2><Names values={user.roles.inherited} /></article><article className="card"><h2>{t('policies')}</h2>{user.is_admin && !user.policies.length ? <p>{t('builtInAdminPolicies')}</p> : <Names values={user.policies} />}</article></div>
      <section className="access-grants"><h2>{t('auditedOpenMetadataGrants')}</h2><p>{t('auditedOpenMetadataGrantsDescription')}</p>{grants.length ? <TemporaryAccessTable grants={grants} canRevoke={Boolean(me?.is_admin)} revokingGrantId={revokingGrantId} onRevoke={revoke} /> : <p className="empty-state">{t('noAuditedOpenMetadataGrants')}</p>}</section>
      <DatabaseAccount associated_database_account={result.associated_database_account} />
    </>}
  </section></Protected>
}
