const DAY = 86_400_000

/** Vietnamese names put the given name last, so "Phạm Quốc Hùng" becomes "QH". */
export const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(-2).map(part => part[0]).join('').toUpperCase()

const startOfDay = (date: Date) => { const copy = new Date(date); copy.setHours(0, 0, 0, 0); return copy }

export type DueState = { tone: 'danger' | 'warning' | 'neutral'; kind: 'overdue' | 'today' | 'businessDaysLeft' | 'on'; count: number; date: Date }

export function dueState(value: string, now = new Date()): DueState {
  const due = startOfDay(new Date(value))
  const today = startOfDay(now)
  const calendarDays = Math.round((due.getTime() - today.getTime()) / DAY)
  if (calendarDays < 0) return { tone: 'danger', kind: 'overdue', count: -calendarDays, date: due }
  if (calendarDays === 0) return { tone: 'warning', kind: 'today', count: 0, date: due }
  let businessDays = 0
  for (let cursor = new Date(today); cursor < due;) {
    cursor.setDate(cursor.getDate() + 1)
    if (cursor.getDay() !== 0 && cursor.getDay() !== 6) businessDays++
  }
  if (businessDays <= 1) return { tone: 'warning', kind: 'businessDaysLeft', count: Math.max(businessDays, 1), date: due }
  return { tone: 'neutral', kind: 'on', count: calendarDays, date: due }
}
