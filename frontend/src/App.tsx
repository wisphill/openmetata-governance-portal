import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AccessPage } from './pages/AccessPage'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { HomePage } from './pages/HomePage'
import { TasksPage } from './pages/TasksPage'

export function App() { return <Routes><Route element={<Layout />}><Route index element={<HomePage />} /><Route path="tasks" element={<TasksPage />} /><Route path="access" element={<AccessPage />} /><Route path="access-denied" element={<AccessDeniedPage />} /></Route></Routes> }
