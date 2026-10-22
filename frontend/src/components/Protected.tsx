import type { PropsWithChildren } from 'react'
import { useTranslation } from 'react-i18next'
import { login } from '../api/client'
import { useAuth } from '../auth/AuthProvider'

export function Protected({ children }: PropsWithChildren) {
  const { me, loading } = useAuth(); const { t } = useTranslation('common')
  if (loading) return <p>{t('loading')}</p>
  if (!me) return <section className="notice"><p>{t('unauthorized')}</p><button onClick={login}>{t('signIn')}</button></section>
  return <>{children}</>
}
