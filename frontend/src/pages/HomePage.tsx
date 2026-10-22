import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthProvider'

export function HomePage() { const { t } = useTranslation('common'); const { me } = useAuth(); return <section className="hero"><p className="eyebrow">{t('source')}</p><h1>{me ? me.identity.display_name ?? me.identity.username : t('appName')}</h1><p>{me ? me.identity.email : t('unauthorized')}</p></section> }
