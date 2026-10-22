import { useTranslation } from 'react-i18next'
import { login } from '../api/client'

export function AccessDeniedPage() {
  const { t } = useTranslation('common')
  return <section className="notice"><p className="eyebrow">403</p><h1>{t('accessDeniedTitle')}</h1><p>{t('accessDenied')}</p><button onClick={login}>{t('signIn')}</button></section>
}
