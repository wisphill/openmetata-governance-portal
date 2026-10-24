import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AccessPage } from './pages/AccessPage'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { ComingSoonPage } from './pages/ComingSoonPage'
import { HomePage } from './pages/HomePage'
import { TasksPage } from './pages/TasksPage'

export function App() { return <Routes><Route element={<Layout />}><Route index element={<HomePage />} /><Route path="tasks" element={<TasksPage />} /><Route path="requests" element={<ComingSoonPage titleKey="myRequests" descriptionKey="myRequestsDescription" />} /><Route path="requests/new" element={<ComingSoonPage titleKey="createRequest" descriptionKey="createRequestDescription" />} /><Route path="access" element={<AccessPage />} /><Route path="query" element={<ComingSoonPage titleKey="query" descriptionKey="queryDescription" />} /><Route path="delegations" element={<ComingSoonPage titleKey="delegation" descriptionKey="delegationDescription" />} /><Route path="authority-matrix" element={<ComingSoonPage titleKey="authorityMatrix" descriptionKey="authorityMatrixDescription" />} /><Route path="access-denied" element={<AccessDeniedPage />} /></Route></Routes> }
