import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { api, login } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import type { TaskPage } from '../types/api'
import { initials } from '../utils/format'
import { Skeleton } from './Skeleton'

type IconName = 'tasks' | 'requests' | 'create' | 'access' | 'userAccess' | 'query' | 'delegation' | 'matrix' | 'catalog' | 'external' | 'menu' | 'chevron'

export function Icon({ name, className = 'nav-icon' }: { name: IconName; className?: string }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  const paths: Record<IconName, ReactNode> = {
    tasks: <><path {...common} d="M3.5 12.5 6 5.5h12l2.5 7v5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1z" /><path {...common} d="M3.5 12.5h5l1.2 2h4.6l1.2-2h5" /></>,
    requests: <path {...common} d="M21 3 3 10.5l7 2.5m11-10-8 18-3-8m11-10L10 13" />,
    create: <><path {...common} d="M14 3.5H7a1 1 0 0 0-1 1v15a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-12z" /><path {...common} d="M14 3.5v4h4M12 11v6M9 14h6" /></>,
    access: <><circle {...common} cx="8" cy="15" r="4" /><path {...common} d="m11 12 9-9m-4 4 3 3m-5-1 2 2" /></>,
    userAccess: <><circle {...common} cx="9" cy="8" r="3.5" /><path {...common} d="M3 20a6 6 0 0 1 12 0M17 10v6m-3-3h6" /></>,
    query: <path {...common} d="m4 7 5 5-5 5m8 0h8" />,
    delegation: <><circle {...common} cx="9" cy="8" r="3.5" /><path {...common} d="M3 20a6 6 0 0 1 10.5-4M16 14l3 3-3 3m3-3h-6" /></>,
    matrix: <><circle {...common} cx="6" cy="5" r="2" /><circle {...common} cx="6" cy="19" r="2" /><circle {...common} cx="18" cy="8" r="2" /><path {...common} d="M6 7v10m12-7c0 4-6 3-11.5 7.5" /></>,
    catalog: <path {...common} d="M4 4v16M8 4v16M12 5l4 15M17 4.5l3.5 15" />,
    external: <path {...common} d="M14 4h6v6m0-6-9 9m7 0v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6" />,
    menu: <path {...common} d="M4 6.5h16M4 12h16M4 17.5h16" />,
    chevron: <path {...common} d="m6 9 6 6 6-6" />,
  }
  return <svg className={className} viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

function BrandLogo() {
  const petals = [-64, -32, 0, 32, 64]
  return <span className="brand-logo" aria-label="Vietnam Airlines">
    <svg className="brand-lotus" viewBox="-26 -24 52 26" aria-hidden="true">
      {petals.map(angle => <path key={angle} transform={`rotate(${angle})`} d={angle === 0 ? 'M0 0C-5-7-5-15 0-22 5-15 5-7 0 0Z' : 'M0 0C-4-6-4-13 0-19 4-13 4-6 0 0Z'} />)}
      <path d="M-14 1.2q14 3 28 0" fill="none" strokeWidth="1.6" />
    </svg>
    <span className="brand-wordmark">Vietnam<span>Airlines</span></span>
  </span>
}

function useTaskCount(enabled: boolean) {
  const [count, setCount] = useState<number>()
  useEffect(() => {
    if (!enabled) return
    api<TaskPage>('/api/tasks').then(page => setCount(page.total ?? page.items.length)).catch(() => setCount(undefined))
  }, [enabled])
  return count
}

function AccountMenu() {
  const { t, i18n } = useTranslation('common')
  const { me, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false) }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('pointerdown', onPointer); document.removeEventListener('keydown', onKey) }
  }, [open])
  if (!me) return null
  const name = me.identity.display_name ?? me.identity.username
  return <div className="account" ref={ref}>
    <button className="account-trigger" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <span className="avatar">{initials(name)}</span>
      <span className="account-name">{name}</span>
      <Icon name="chevron" className="account-chevron" />
    </button>
    {open && <div className="account-menu" role="menu">
      <div className="account-menu__identity"><strong>{name}</strong><span>{me.identity.email ?? me.identity.username}</span></div>
      <label className="account-menu__row">{t('language')}
        <select value={i18n.language} onChange={event => void i18n.changeLanguage(event.target.value)}><option value="vi">Tiếng Việt</option><option value="en">English</option></select>
      </label>
      <button className="account-menu__item" role="menuitem" onClick={() => { setOpen(false); void logout() }}>{t('signOut')}</button>
    </div>}
  </div>
}

export function Layout() {
  const { t } = useTranslation('common')
  const { me, loading } = useAuth()
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)
  const taskCount = useTaskCount(Boolean(me))
  const catalogUrl = import.meta.env.VITE_OPENMETADATA_URL as string | undefined
  useEffect(() => setNavOpen(false), [location.pathname])
  const navItems: Array<{ to: string; icon: IconName; label: string; badge?: number }> = [
    { to: '/tasks', icon: 'tasks', label: t('tasks'), badge: taskCount },
    { to: '/requests', icon: 'requests', label: t('myRequests') },
    { to: '/requests/new', icon: 'create', label: t('createRequest') },
    { to: '/data-products', icon: 'catalog', label: 'Data Products' },
    { to: '/access', icon: 'access', label: t('dataAccess') },
    { to: '/user-access', icon: 'userAccess', label: t('userAccess') },
    { to: '/query', icon: 'query', label: t('query') },
    { to: '/delegations', icon: 'delegation', label: t('delegation') },
    { to: '/authority-matrix', icon: 'matrix', label: t('authorityMatrix') },
  ]
  return <div className={`app-shell${navOpen ? ' app-shell--nav-open' : ''}`}>
    <header className="app-header">
      <button className="menu-toggle" aria-label={t('navigation')} aria-expanded={navOpen} onClick={() => setNavOpen(value => !value)}><Icon name="menu" /></button>
      <Link className="brand" to="/"><BrandLogo /><span className="brand-divider" /><span className="brand-product">{t('appName')}</span></Link>
      <div className="header-spacer" />
      {loading ? <Skeleton className="skeleton--account" /> : me ? <AccountMenu /> : <button className="sign-in" onClick={login}>{t('signIn')}</button>}
    </header>
    <div className="app-body">
      <div className="nav-scrim" onClick={() => setNavOpen(false)} />
      <aside className="sidebar" aria-label={t('navigation')}>
        <p className="nav-group-title">{t('work')}</p>
        {loading ? <><Skeleton className="skeleton--nav" /><Skeleton className="skeleton--nav" /><Skeleton className="skeleton--nav" /></> : <nav className="primary-nav">
          {navItems.map(item => <NavLink key={item.to} to={item.to} end><Icon name={item.icon} /><span className="nav-label">{item.label}</span>{item.badge ? <span className="nav-badge">{item.badge}</span> : null}</NavLink>)}
        </nav>}
        <p className="nav-group-title nav-group-title--spaced">{t('links')}</p>
        {catalogUrl
          ? <a className="catalog-link" href={catalogUrl} target="_blank" rel="noreferrer"><Icon name="catalog" /><span className="nav-label">{t('catalog')}</span><Icon name="external" className="nav-icon nav-icon--trailing" /></a>
          : <span className="catalog-link catalog-link--disabled"><Icon name="catalog" /><span className="nav-label">{t('catalog')}</span><Icon name="external" className="nav-icon nav-icon--trailing" /></span>}
      </aside>
      <main className="app-content"><Outlet /></main>
    </div>
  </div>
}
