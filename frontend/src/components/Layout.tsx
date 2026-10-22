import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { login } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

export function Layout() {
  const { t, i18n } = useTranslation('common'); const { me, loading, logout } = useAuth()
  return <main className="shell"><header><Link className="brand" to="/">{t('appName')}</Link><nav>{me && <><Link to="/tasks">{t('tasks')}</Link><Link to="/access">{t('access')}</Link></>}</nav><div className="actions"><select aria-label={t('language')} value={i18n.language} onChange={event => void i18n.changeLanguage(event.target.value)}><option value="en">English</option><option value="vi">Tiếng Việt</option></select>{!loading && (me ? <button onClick={() => void logout()}>{t('signOut')}</button> : <button onClick={login}>{t('signIn')}</button>)}</div></header><Outlet /></main>
}
