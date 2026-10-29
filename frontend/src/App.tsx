import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AccessPage } from './pages/AccessPage'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { HomePage } from './pages/HomePage'
import { TasksPage } from './pages/TasksPage'
import { CreateAccessRequestPage } from './pages/CreateAccessRequestPage'
import { MyRequestsPage } from './pages/MyRequestsPage'
import { UserAccessPage } from './pages/UserAccessPage'
import { DataProductsPage } from './pages/DataProductsPage'

const QueryPage = lazy(() => import('./pages/QueryPage').then(module => ({ default: module.QueryPage })))

export function App() { return <Routes><Route element={<Layout />}><Route index element={<HomePage />} /><Route path="tasks" element={<TasksPage />} /><Route path="requests" element={<MyRequestsPage />} /><Route path="requests/new" element={<CreateAccessRequestPage />} /><Route path="data-products" element={<DataProductsPage />} /><Route path="access" element={<AccessPage />} /><Route path="user-access" element={<UserAccessPage />} /><Route path="query" element={<Suspense fallback={<main className="page">Loading query editor…</main>}><QueryPage /></Suspense>} /><Route path="delegations" element={<ComingSoonPage titleKey="delegation" descriptionKey="delegationDescription" />} /><Route path="authority-matrix" element={<ComingSoonPage titleKey="authorityMatrix" descriptionKey="authorityMatrixDescription" />} /><Route path="access-denied" element={<AccessDeniedPage />} /></Route></Routes> }
