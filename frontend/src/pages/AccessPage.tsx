import { useTranslation } from 'react-i18next'
import { Protected } from '../components/Protected'
import { useAuth } from '../auth/AuthProvider'

function Names({ values }: { values: Array<Record<string, unknown>> }) { return values.length ? <ul>{values.map((value, index) => <li key={String(value.id ?? index)}>{String(value.name ?? value.displayName ?? value.id ?? '')}</li>)}</ul> : <p>—</p> }
export function AccessPage() { const { t } = useTranslation('common'); const { me } = useAuth(); return <Protected><section><p className="eyebrow">{t('source')}</p><h1>{t('access')}</h1><div className="grid"><article><h2>{t('teams')}</h2><Names values={me?.teams ?? []} /></article><article><h2>{t('directRoles')}</h2><Names values={me?.roles.direct ?? []} /></article><article><h2>{t('inheritedRoles')}</h2><Names values={me?.roles.inherited ?? []} /></article><article><h2>{t('policies')}</h2>{me?.is_admin && !me.policies.length ? <p>{t('builtInAdminPolicies')}</p> : <Names values={me?.policies ?? []} />}</article></div></section></Protected> }
