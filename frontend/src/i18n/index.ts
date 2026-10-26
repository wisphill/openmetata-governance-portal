import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import enCommon from './locales/en/common.json'
import enTasks from './locales/en/tasks.json'
import viCommon from './locales/vi/common.json'
import viTasks from './locales/vi/tasks.json'
import enRequests from './locales/en/requests.json'
import viRequests from './locales/vi/requests.json'
import enGrants from './locales/en/grants.json'
import viGrants from './locales/vi/grants.json'

i18n.use(initReactI18next).init({ resources: { en: { common: enCommon, tasks: enTasks, requests: enRequests, grants: enGrants }, vi: { common: viCommon, tasks: viTasks, requests: viRequests, grants: viGrants } }, lng: navigator.language.startsWith('vi') ? 'vi' : 'en', fallbackLng: 'en', ns: ['common', 'tasks', 'requests', 'grants'], defaultNS: 'common', interpolation: { escapeValue: false } })
export default i18n
