import { dateLocale, has, t } from '../i18n'

// Khmer month names – formatted by hand so every browser shows the same result
const KM_MONTHS = ['មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']
const isKm = () => dateLocale() === 'km-KH'
const pad = (n) => String(n).padStart(2, '0')
const kmDate = (d) => `${pad(d.getDate())} ${KM_MONTHS[d.getMonth()]} ${d.getFullYear()}`
const kmTime = (d) => `ម៉ោង ${pad(d.getHours())}:${pad(d.getMinutes())}`

export function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isKm()) return `${kmDate(d)} ${kmTime(d)}`
  return d.toLocaleString(dateLocale(), { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isKm()) return kmDate(d)
  return d.toLocaleDateString(dateLocale(), { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isKm()) return `${pad(d.getHours())}:${pad(d.getMinutes())}`
  return d.toLocaleTimeString(dateLocale(), { hour: '2-digit', minute: '2-digit' })
}

export function fmtMonth(date) {
  const d = new Date(date)
  if (isKm()) return KM_MONTHS[d.getMonth()]
  return d.toLocaleDateString(dateLocale(), { month: 'short' })
}

export function fromNow(iso) {
  if (!iso) return ''
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(diff)
  const units = [[86400, 'day'], [3600, 'hour'], [60, 'minute']]
  for (const [secs, name] of units) {
    if (abs >= secs) {
      const n = Math.round(abs / secs)
      const unit = t(`time.${name}${n > 1 ? 's' : ''}`)
      return diff > 0 ? t('time.in', { n, unit }) : t('time.ago', { n, unit })
    }
  }
  return diff > 0 ? t('time.soon') : t('time.justNow')
}

// Value for <input type="datetime-local"> from an ISO string (local time)
export function toLocalInput(iso) {
  const d = iso ? new Date(iso) : new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Local datetime-input value -> ISO with timezone (UTC)
export function fromLocalInput(value) {
  return value ? new Date(value).toISOString() : null
}

export function bytes(n) {
  if (!n && n !== 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** Display text for a status / type value such as "unexcused" or "strictly_confidential". */
export const label = (s) => {
  if (s === null || s === undefined || s === '') return ''
  const key = 'enums.' + String(s)
  if (has(key)) return t(key)
  return String(s).replace(/[_.]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export const initials = (name) => (name || '?').split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase()
