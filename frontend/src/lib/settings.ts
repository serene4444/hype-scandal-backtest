// Form settings <-> URL query <-> API request, so "Edit settings" on Results can reopen the form filled in.
import { EARLIEST_DATES, type BacktestRequest, type StrategyId, type Ticker } from '../api/backtests'

export interface Settings {
  ticker: Ticker
  strategy: StrategyId
  dropPct: number // whole percent, 1-20
  upDays: number // 1-10
  start: string
  amount: string // as typed, e.g. "$1,000"
  compare: boolean
}

export const DEFAULT_START: Record<Ticker, string> = { META: '2020-01-02', PLTR: EARLIEST_DATES.PLTR }
export const DIP_LOOKBACK_DAYS = 5 // "weekly"
export const DIP_MAX_HOLD_DAYS = 60
const STRATEGIES: StrategyId[] = ['buy_the_dip', 'ride_the_hype', 'buy_and_hold']

const clampInt = (raw: string | null, lo: number, hi: number, fallback: number) => {
  const n = Math.round(Number(raw))
  return raw !== null && Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : fallback
}

export function settingsFromQuery(query: URLSearchParams): Settings {
  const ticker: Ticker = query.get('ticker') === 'PLTR' ? 'PLTR' : 'META'
  const strategy = STRATEGIES.find((s) => s === query.get('strategy')) ?? 'buy_the_dip'
  const amount = Number(query.get('amount'))
  return {
    ticker,
    strategy,
    dropPct: clampInt(query.get('drop'), 1, 20, 5),
    upDays: clampInt(query.get('up_days'), 1, 10, 3),
    start: /^\d{4}-\d{2}-\d{2}$/.test(query.get('start') ?? '') ? query.get('start')! : DEFAULT_START[ticker],
    amount: formatAmountInput(Number.isFinite(amount) && amount > 0 ? amount : 1000),
    compare: query.get('compare') !== '0',
  }
}

export function queryFromRequest(request: BacktestRequest, compare: boolean): string {
  const query = new URLSearchParams({
    ticker: request.ticker,
    strategy: request.strategy,
    start: request.start_date,
    amount: String(request.amount),
  })
  if (request.params.drop_pct !== undefined) query.set('drop', String(Math.round(request.params.drop_pct * 100)))
  if (request.params.up_days !== undefined) query.set('up_days', String(request.params.up_days))
  if (!compare) query.set('compare', '0')
  return query.toString()
}

export const parseAmount = (text: string): number => Number(text.replace(/[^0-9.]/g, ''))

export const formatAmountInput = (value: number): string =>
  `$${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}`

export function requestFromSettings(s: Settings): BacktestRequest {
  const params: Record<string, number> =
    s.strategy === 'buy_the_dip'
      ? { drop_pct: s.dropPct / 100, lookback: DIP_LOOKBACK_DAYS, max_hold_days: DIP_MAX_HOLD_DAYS }
      : s.strategy === 'ride_the_hype'
        ? { up_days: s.upDays }
        : {}
  return { ticker: s.ticker, strategy: s.strategy, params, start_date: s.start, amount: parseAmount(s.amount), fee: 1 }
}
