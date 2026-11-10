import { useEffect, useMemo, useRef, useState } from 'react'
import { getBacktest, type BacktestDetail } from '../api/backtests'
import { ApiError } from '../api/client'
import { ClaudeAnalysis } from '../components/ClaudeAnalysis'
import { EquityChart } from '../components/EquityChart'
import { SpinnerIcon, WarningIcon } from '../components/Icons'
import { Link } from '../components/Link'
import { loadAgentRun } from '../lib/agentRuns'
import { EVENTS } from '../lib/events'
import {
  COMPANY,
  describeRule,
  formatMoney,
  formatMoneyCents,
  formatPct,
  formatRecovery,
  runTitle,
} from '../lib/format'
import { queryFromRequest } from '../lib/settings'
import { useLocation } from '../router'

type Load = { kind: 'loading' } | { kind: 'error'; message: string; missing: boolean } | { kind: 'done'; data: BacktestDetail }

export function Results({ id }: { id: string }) {
  const { query } = useLocation()
  const compare = query.get('compare') !== '0'
  const [load, setLoad] = useState<Load>({ kind: 'loading' })
  const titleRef = useRef<HTMLHeadingElement>(null)
  const agentRun = useMemo(() => loadAgentRun(id), [id])

  useEffect(() => {
    // The page is keyed by id in App, so a new id remounts it and starts from 'loading'.
    const controller = new AbortController()
    getBacktest(id, controller.signal)
      .then((data) => setLoad({ kind: 'done', data }))
      .catch((error) => {
        if (controller.signal.aborted) return
        const missing = error instanceof ApiError && error.status === 404
        setLoad({ kind: 'error', missing, message: error instanceof ApiError ? error.message : 'Could not load results.' })
      })
    return () => controller.abort()
  }, [id])

  useEffect(() => {
    if (load.kind === 'done') {
      document.title = `${runTitle(load.data.request)} · Hype vs. Scandal`
      titleRef.current?.focus()
    }
  }, [load])

  if (load.kind === 'loading') {
    return (
      <div className="notice" role="status">
        <SpinnerIcon /> Loading results…
      </div>
    )
  }

  if (load.kind === 'error') {
    return (
      <div className="results-missing">
        <div className="notice notice-error" role="alert">
          <WarningIcon />
          {load.missing
            ? 'This backtest is no longer stored. Results are kept in memory, so they disappear when the server restarts.'
            : load.message}
        </div>
        <Link to="/backtest" className="button button-secondary">
          Run a backtest
        </Link>
      </div>
    )
  }

  const { request, metrics, equity_curve: curve, trades } = load.data
  const lastDay = curve.at(-1)?.date ?? ''
  const holdEnd = curve.at(-1)?.buy_and_hold ?? 0
  const lowest = Math.min(...curve.map((p) => p.strategy))

  return (
    <div className="results">
      <div className="results-head">
        <div className="results-title">
          <span className="section-label">
            {request.ticker} · {request.start_date} to {lastDay} · {formatMoney(request.amount)} ·{' '}
            {describeRule(request.strategy, request.params)}
          </span>
          <h1 ref={titleRef} tabIndex={-1}>
            {runTitle(request)}
          </h1>
        </div>
        <div className="results-actions">
          <Link to={`/backtest?${queryFromRequest(request, compare)}`} className="button button-secondary">
            Edit settings
          </Link>
        </div>
      </div>

      <section aria-label="Scorecard" className="scorecard">
        <div className="tile tile-highlight">
          <span className="tile-label">{formatMoney(request.amount)} became</span>
          <span className="figure">{formatMoneyCents(metrics.ending_value)}</span>
          <span className="tile-sub">Buy-and-hold: {formatMoneyCents(holdEnd)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">Total return</span>
          <span className="figure">{formatPct(metrics.total_return, true)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">Biggest drop</span>
          <span className="figure">{formatPct(metrics.max_drawdown)}</span>
          <span className="tile-sub">Lowest point: {formatMoneyCents(lowest)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">Time to recover</span>
          <span className="figure">{formatRecovery(metrics.time_to_recover)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">Trades · Sharpe</span>
          <span className="figure">
            {metrics.trade_count} · {metrics.sharpe.toFixed(1)}
          </span>
        </div>
      </section>

      <EquityChart
        curve={curve}
        trades={trades}
        events={EVENTS[request.ticker]}
        amount={request.amount}
        showBuyAndHold={compare}
      />

      <div className="results-columns">
        <ClaudeAnalysis run={agentRun} />

        <section aria-labelledby="trades-heading" className="card trade-log">
          <h2 id="trades-heading" className="section-label">
            Trade log · {trades.length} trade{trades.length === 1 ? '' : 's'}
          </h2>
          {trades.length === 0 ? (
            <p className="muted">No trades: the rule never triggered on {COMPANY[request.ticker]} in this period.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Action</th>
                    <th scope="col">Shares</th>
                    <th scope="col">Price</th>
                    <th scope="col">Cash left</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={`${trade.date}-${trade.action}`}>
                      <td>{trade.date}</td>
                      <td>
                        <span className="trade-action">
                          <svg width="10" height="10" aria-hidden="true">
                            <polygon points={trade.action === 'BUY' ? '5,0 10,10 0,10' : '0,0 10,0 5,10'} fill="currentColor" />
                          </svg>
                          {trade.action}
                        </span>
                      </td>
                      <td>{trade.shares}</td>
                      <td>{formatMoneyCents(trade.price)}</td>
                      <td>{formatMoneyCents(trade.cash_left)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <span className="help">Whole shares only; leftover cash carries over. Fees included.</span>
        </section>
      </div>

      <p className="disclaimer">Simulation only. Not financial advice. No real money is traded.</p>
    </div>
  )
}
