// Backtest and price endpoints. Shapes mirror backend/app/api/backtests.py and prices.py.
import { request } from './client'

export type Ticker = 'META' | 'PLTR'
export type StrategyId = 'buy_the_dip' | 'ride_the_hype' | 'buy_and_hold'

export const EARLIEST_DATES: Record<Ticker, string> = { META: '2012-05-18', PLTR: '2020-09-30' }
export const MIN_AMOUNT = 100
export const MAX_AMOUNT = 1_000_000

export interface BacktestRequest {
  ticker: Ticker
  strategy: StrategyId
  params: Record<string, number>
  start_date: string
  end_date?: string | null
  amount: number
  fee: number
}

export interface Metrics {
  ending_value: number
  total_return: number
  max_drawdown: number
  time_to_recover: number | null
  sharpe: number
  trade_count: number
}

export interface BacktestSummary {
  id: string
  ticker: Ticker
  strategy: StrategyId
  metrics: Metrics
  cached: boolean
}

export interface CurvePoint {
  date: string
  strategy: number
  buy_and_hold: number
}

export interface Trade {
  date: string
  action: 'BUY' | 'SELL'
  shares: number
  price: number
  fee: number
  cash_left: number
}

export interface BacktestDetail extends BacktestSummary {
  request: BacktestRequest
  equity_curve: CurvePoint[]
  trades: Trade[]
}

export interface PricePoint {
  date: string
  close: number
}

export const runBacktest = (body: BacktestRequest) =>
  request<BacktestSummary>('/backtests', { method: 'POST', body: JSON.stringify(body) })

export const getBacktest = (id: string, signal?: AbortSignal) =>
  request<BacktestDetail>(`/backtests/${encodeURIComponent(id)}`, { signal })

export const getPrices = (ticker: Ticker, start: string, signal?: AbortSignal) =>
  request<{ ticker: Ticker; points: PricePoint[] }>(`/prices/${ticker}?start=${start}&every=5`, { signal })
