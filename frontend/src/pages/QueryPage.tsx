import Editor from '@monaco-editor/react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { format } from 'sql-formatter'
import { api, ApiError } from '../api/client'
import { Protected } from '../components/Protected'
import type { QueryResult } from '../types/api'

const initialSql = 'SELECT customer_id, email, full_name, country_code, created_at\nFROM app.customers\nFETCH FIRST 10 ROWS ONLY;'

export function QueryPage() {
  const { t } = useTranslation('query')
  const [sql, setSql] = useState(initialSql)
  const [result, setResult] = useState<QueryResult>()
  const [error, setError] = useState<string>()
  const [running, setRunning] = useState(false)

  const prettify = () => {
    try { setSql(format(sql, { language: 'sql' })); setError(undefined) }
    catch { setError(t('formatFailed')) }
  }
  const run = async () => {
    if (!sql.trim()) return
    setRunning(true); setError(undefined)
    try { setResult(await api<QueryResult>('/api/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sql }) })) }
    catch (err) { if (!(err instanceof ApiError && err.status === 401)) setError(err instanceof ApiError && err.message !== 'requestFailed' ? err.message : t('queryFailed')) }
    finally { setRunning(false) }
  }
  const displayValue = (value: unknown) => value === null ? 'NULL' : typeof value === 'object' ? JSON.stringify(value) : String(value)

  return <Protected><section className="page page--query">
    <div className="page-header"><div><h1>{t('title')}</h1><p>{t('description')}</p></div></div>
    <section className="query-editor-panel" aria-label={t('editorLabel')}>
      <div className="query-editor-toolbar"><span>SQL</span><div><button className="button-secondary" onClick={prettify}>{t('prettify')}</button><button className="button-primary" disabled={running || !sql.trim()} onClick={() => void run()}>{running ? t('running') : t('run')}</button></div></div>
      <Editor height="360px" language="sql" value={sql} onChange={value => setSql(value ?? '')} options={{ automaticLayout: true, fontSize: 14, lineNumbers: 'on', minimap: { enabled: false }, scrollBeyondLastLine: false, tabSize: 2, wordWrap: 'on' }} />
    </section>
    {error && <p className="alert" role="alert">{error}</p>}
    <section className="query-results" aria-live="polite"><div><h2>{t('results')}</h2><p>{t('resultsDescription')}</p></div>{!result && <p className="empty-state">{t('emptyResults')}</p>}{result && <><div className="query-result-meta">{result.is_dummy && <span className="pill">{t('sampleResult')}</span>}<span>{t('rowCount', { count: result.row_count })}</span></div><p className="query-result-message">{result.message}</p><div className="table-wrap query-results-table"><table><thead><tr>{result.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.items.map((item, rowIndex) => <tr key={rowIndex}>{result.columns.map(column => <td key={column}>{displayValue(item[column])}</td>)}</tr>)}</tbody></table></div></>}</section>
  </section></Protected>
}
