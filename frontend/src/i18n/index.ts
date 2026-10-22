import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import enCommon from './locales/en/common.json'
import enTasks from './locales/en/tasks.json'
import viCommon from './locales/vi/common.json'
import viTasks from './locales/vi/tasks.json'

i18n.use(initReactI18next).init({ resources: { en: { common: enCommon, tasks: enTasks }, vi: { common: viCommon, tasks: viTasks } }, lng: navigator.language.startsWith('vi') ? 'vi' : 'en', fallbackLng: 'en', ns: ['common', 'tasks'], defaultNS: 'common', interpolation: { escapeValue: false } })
export default i18n
