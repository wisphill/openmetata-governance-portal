import { useTranslation } from 'react-i18next'
import { Protected } from '../components/Protected'

export function ComingSoonPage({ titleKey, descriptionKey }: { titleKey: string; descriptionKey: string }) {
  const { t } = useTranslation('common')
  return <Protected><section className="page"><div className="page-header"><div><h1>{t(titleKey)}</h1><p>{t(descriptionKey)}</p></div></div><div className="empty-state"><p>{t('notConnected')}</p></div></section></Protected>
}
