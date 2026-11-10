const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const moneyCents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })

export const formatMoney = (value: number): string => money.format(value)
export const formatMoneyCents = (value: number): string => moneyCents.format(value)

/** 0.253 -> "+25.3%" (sign shown when ``signed``). */
export function formatPct(fraction: number, signed = false): string {
  const pct = fraction * 100
  const text = `${Math.abs(pct) >= 100 ? pct.toFixed(0) : pct.toFixed(1)}%`
  if (signed && pct > 0) return `+${text}`
  return text.replace('-', '−')
}

export function formatDays(days: number | null): string {
  if (days === null) return 'Not yet'
  if (days === 0) return 'No drop'
  return `${days} trading day${days === 1 ? '' : 's'}`
}

export const STRATEGY_LABELS: Record<string, string> = {
  buy_and_hold: 'Buy and hold',
  buy_the_dip: 'Buy the dip',
  ride_the_hype: 'Ride the hype',
}

export const TICKER_LABELS: Record<string, string> = { META: 'Meta', PLTR: 'Palantir' }

export function describeParams(params: Record<string, unknown> | undefined): string[] {
  if (!params) return []
  const parts: string[] = []
  const num = (key: string) => (typeof params[key] === 'number' ? (params[key] as number) : undefined)
  const drop = num('drop_pct')
  const lookback = num('lookback')
  const maxHold = num('max_hold_days')
  const upDays = num('up_days')
  if (drop !== undefined) parts.push(`${Number((drop * 100).toFixed(1))}% drop`)
  if (lookback !== undefined) parts.push(`from ${lookback}-day high`)
  if (maxHold !== undefined) parts.push(`hold up to ${maxHold} days`)
  if (upDays !== undefined) parts.push(`${upDays} days in a row`)
  return parts
}
