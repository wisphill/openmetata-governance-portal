import { Link, NavLink, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { login } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { Skeleton } from './Skeleton'

type IconName = 'tasks' | 'requests' | 'create' | 'access' | 'query' | 'external'

function NavigationIcon({ name }: { name: IconName }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  const paths: Record<IconName, ReactNode> = {
    tasks: <><path {...common} d="M4 8.5h16l-1.4 9H5.4L4 8.5Z" /><path {...common} d="M8 8.5V7a4 4 0 0 1 8 0v1.5M4 13h4l1.2 2h5.6l1.2-2h4" /></>,
    requests: <><path {...common} d="m3 4 18 8-7.4 2.4L11.2 21 3 4Z" /><path {...common} d="m13.6 14.4 3.2-3.2" /></>,
    create: <><path {...common} d="M6 3.5h8l4 4V20.5H6z" /><path {...common} d="M14 3.5v4h4M12 11v6M9 14h6" /></>,
    access: <><circle {...common} cx="9" cy="12" r="3.5" /><path {...common} d="m11.5 14.5 7 7M15.5 18.5l2-2M17.5 20.5l2-2" /></>,
    query: <><path {...common} d="m8 5-6 7 6 7M16 5l6 7-6 7M10 20l4-16" /></>,
    external: <><path {...common} d="M14 4h6v6M20 4l-9 9M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6" /></>,
  }
  return <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

export function Layout() {
  const { t, i18n } = useTranslation('common')
  const { me, loading, logout } = useAuth()
  const initials = me?.identity.display_name?.split(/\s+/).map(name => name[0]).join('').slice(0, 2) ?? me?.identity.username.slice(0, 2).toUpperCase()
  const catalogUrl = import.meta.env.VITE_OPENMETADATA_URL as string | undefined
  return <main className="app-shell"><header className="app-header"><Link className="brand" to="/"><span className="brand-emblem" aria-hidden="true">✦</span><span className="brand-wordmark">Vietnam Airlines</span><span className="brand-divider" /><span className="brand-product">{t('appName')}</span></Link><div className="header-spacer" /><select className="language-select" aria-label={t('language')} value={i18n.language} onChange={event => void i18n.changeLanguage(event.target.value)}><option value="en">English</option><option value="vi">Tiếng Việt</option></select>{loading ? <Skeleton className="skeleton--account" /> : me ? <div className="account"><span className="avatar" title={me.identity.display_name ?? me.identity.username}>{initials}</span><span className="account-name">{me.identity.display_name ?? me.identity.username}</span><button className="sign-out" onClick={() => void logout()} title={t('signOut')} aria-label={t('signOut')}>⌄</button></div> : <button className="sign-in" onClick={login}>{t('signIn')}</button>}</header><div className="app-body"><aside className="sidebar" aria-label={t('navigation')}><p className="nav-group-title">{t('work')}</p>{loading ? <><Skeleton className="skeleton--nav" /><Skeleton className="skeleton--nav" /><Skeleton className="skeleton--nav" /></> : <nav className="primary-nav"><NavLink to="/tasks"><NavigationIcon name="tasks" />{t('tasks')}</NavLink><NavLink to="/requests"><NavigationIcon name="requests" />{t('myRequests')}</NavLink><NavLink to="/requests/new"><NavigationIcon name="create" />{t('createRequest')}</NavLink><NavLink to="/access"><NavigationIcon name="access" />{t('dataAccess')}</NavLink><NavLink to="/query"><NavigationIcon name="query" />{t('query')}</NavLink></nav>}<div className="sidebar-footer"><p className="nav-group-title">{t('links')}</p>{catalogUrl ? <a className="catalog-link" href={catalogUrl} target="_blank" rel="noreferrer"><span className="catalog-glyph" aria-hidden="true">▥</span>{t('catalog')}<NavigationIcon name="external" /></a> : <span className="catalog-link catalog-link--disabled"><span className="catalog-glyph" aria-hidden="true">▥</span>{t('catalog')}</span>}</div></aside><main className="app-content"><Outlet /></main></div></main>
}
