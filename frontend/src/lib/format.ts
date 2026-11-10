import type { BacktestRequest, StrategyId, Ticker } from '../api/backtests'

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const moneyCents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

export const formatMoney = (value: number): string => money.format(value)
export const formatMoneyCents = (value: number): string => moneyCents.format(value)

/** 0.253 -> "+25.3%" (sign shown when ``signed``); minus signs are typographic. */
export function formatPct(fraction: number, signed = false): string {
  const pct = fraction * 100
  const text = `${Math.abs(pct) >= 100 ? pct.toFixed(0) : pct.toFixed(1)}%`
  if (signed && pct > 0) return `+${text}`
  return text.replace('-', '−')
}

/** Whole-number percent without a trailing ".0", e.g. 0.07 -> "7%". */
export const shortPct = (fraction: number): string => `${Number((fraction * 100).toFixed(1))}%`

const TRADING_DAYS_PER_MONTH = 21

export function formatRecovery(days: number | null): string {
  if (days === null) return 'Not yet'
  if (days === 0) return 'No drop'
  if (days < TRADING_DAYS_PER_MONTH) return `${days} day${days === 1 ? '' : 's'}`
  return `${Math.round(days / TRADING_DAYS_PER_MONTH)} mo`
}

export const STRATEGY_LABELS: Record<StrategyId, string> = {
  buy_the_dip: 'Buy the dip',
  ride_the_hype: 'Ride the hype',
  buy_and_hold: 'Buy-and-hold',
}

export const COMPANY: Record<Ticker, string> = { META: 'Meta', PLTR: 'Palantir' }

/** Short description of a run's rule, e.g. "7% weekly drop" or "3 up days in a row". */
export function describeRule(strategy: StrategyId, params: Record<string, number>): string {
  if (strategy === 'buy_the_dip') {
    const drop = shortPct(params.drop_pct ?? 0.1)
    const lookback = params.lookback ?? 20
    const window = lookback === 5 ? 'weekly' : lookback === 21 ? 'monthly' : `${lookback}-day`
    return `${drop} ${window} drop`
  }
  if (strategy === 'ride_the_hype') return `${params.up_days ?? 3} up days in a row`
  return 'hold from day one'
}

export const runTitle = (request: BacktestRequest): string =>
  `${STRATEGY_LABELS[request.strategy]} on ${COMPANY[request.ticker]}`
