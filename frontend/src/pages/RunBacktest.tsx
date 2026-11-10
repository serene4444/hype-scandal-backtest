import { useEffect, useRef, useState, type FormEvent } from 'react'
import { finalBacktestId, MAX_PROMPT_LENGTH, runRule, type RuleResponse } from '../api/agent'
import { EARLIEST_DATES, MAX_AMOUNT, MIN_AMOUNT, runBacktest, type StrategyId, type Ticker } from '../api/backtests'
import { ApiError } from '../api/client'
import { ClaudeAnswer } from '../components/ClaudeAnalysis'
import { SpinnerIcon, WarningIcon } from '../components/Icons'
import { PricePreview } from '../components/PricePreview'
import { saveAgentRun } from '../lib/agentRuns'
import { COMPANY, formatMoney } from '../lib/format'
import {
  DIP_MAX_HOLD_DAYS,
  formatAmountInput,
  parseAmount,
  requestFromSettings,
  settingsFromQuery,
  type Settings,
} from '../lib/settings'
import { navigate, useLocation } from '../router'

type Mode = 'settings' | 'english'

export function RunBacktest() {
  const { query } = useLocation()
  const [mode, setMode] = useState<Mode>(query.get('mode') === 'english' ? 'english' : 'settings')

  return (
    <div className="run-layout">
      <div className="card form-panel">
        <h2 className="section-label">Run a backtest</h2>
        <div className="segmented" role="group" aria-label="How to set the rule">
          <button type="button" aria-pressed={mode === 'settings'} onClick={() => setMode('settings')}>
            Pick settings
          </button>
          <button type="button" aria-pressed={mode === 'english'} onClick={() => setMode('english')}>
            Plain English
          </button>
        </div>
        {mode === 'settings' ? <SettingsForm initial={settingsFromQuery(query)} /> : <PlainEnglishForm />}
      </div>

      <section className="hero" aria-labelledby="hero-title">
        <span className="section-label">Meta · Palantir · 2020 to today</span>
        <h1 id="hero-title">Would this rule have turned $1,000 into more than just holding the stock?</h1>
        <p className="hero-lede">
          Test trading rules on Meta, the scandal comeback, and Palantir, the hype rocket. Then see if they beat
          buy-and-hold and 1,000 random monkeys.
        </p>
        <PricePreview />
        <ol className="how-steps">
          <li>
            <span className="step-num">01</span>
            <span className="step-title">Pick a stock and a rule</span>
            <span className="step-text">Buy the dip, ride the hype, or describe your own</span>
          </li>
          <li>
            <span className="step-num">02</span>
            <span className="step-title">Replay every trading day</span>
            <span className="step-text">Only using prices known on that day</span>
          </li>
          <li>
            <span className="step-num">03</span>
            <span className="step-title">See if it was skill or luck</span>
            <span className="step-text">Against buy-and-hold and 1,000 monkeys</span>
          </li>
        </ol>
        <p className="disclaimer">Simulation only. Not financial advice. No real money is traded.</p>
      </section>
    </div>
  )
}

/* ---------------- Pick settings ---------------- */

type FieldErrors = Partial<Record<'start' | 'amount' | 'form', string>>

const today = () => new Date().toISOString().slice(0, 10)

function validate(s: Settings): FieldErrors {
  const errors: FieldErrors = {}
  const earliest = EARLIEST_DATES[s.ticker]
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s.start)) errors.start = 'Enter a date like 2020-01-02'
  else if (s.start < earliest) errors.start = `${COMPANY[s.ticker]} data starts ${earliest}`
  else if (s.start >= today()) errors.start = 'Start date must be in the past'
  const amount = parseAmount(s.amount)
  if (!Number.isFinite(amount) || amount < MIN_AMOUNT || amount > MAX_AMOUNT) {
    errors.amount = `Enter an amount from ${formatMoney(MIN_AMOUNT)} to ${formatMoney(MAX_AMOUNT)}`
  }
  return errors
}

function SettingsForm({ initial }: { initial: Settings }) {
  const [s, setS] = useState<Settings>(initial)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [running, setRunning] = useState(false)
  const update = (patch: Partial<Settings>) => setS((prev) => ({ ...prev, ...patch }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const found = validate(s)
    setErrors(found)
    if (Object.keys(found).length) return
    setRunning(true)
    try {
      const summary = await runBacktest(requestFromSettings(s))
      navigate(`/results/${summary.id}${s.compare ? '' : '?compare=0'}`)
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Something went wrong. Try again.'
      const field = error instanceof ApiError ? error.field : undefined
      setErrors(field === 'start_date' ? { start: message } : field === 'amount' ? { amount: message } : { form: message })
      setRunning(false)
    }
  }

  return (
    <form className="settings-form" onSubmit={submit} aria-label="Backtest settings" noValidate>
      <fieldset className="field">
        <legend>Stock</legend>
        <div className="stock-toggle">
          {(['META', 'PLTR'] as Ticker[]).map((ticker) => (
            <button
              key={ticker}
              type="button"
              aria-pressed={s.ticker === ticker}
              onClick={() => {
                // Palantir only has data from its listing day, so move an earlier start date forward.
                const earliest = EARLIEST_DATES[ticker]
                update({ ticker, start: s.start < earliest ? earliest : s.start })
                setErrors((prev) => ({ ...prev, start: undefined }))
              }}
            >
              {ticker}
            </button>
          ))}
        </div>
      </fieldset>

      <div className="field">
        <label htmlFor="strategy">Strategy</label>
        <select id="strategy" value={s.strategy} onChange={(e) => update({ strategy: e.target.value as StrategyId })}>
          <option value="buy_the_dip">Buy the dip</option>
          <option value="ride_the_hype">Ride the hype</option>
          <option value="ml_rule" disabled>
            ML rule (coming soon)
          </option>
          <option value="buy_and_hold">Buy-and-hold</option>
        </select>
      </div>

      {s.strategy === 'buy_the_dip' && (
        <div className="field">
          <div className="range-label">
            <label htmlFor="drop">Buy after a weekly drop of</label>
            <span className="mono">{s.dropPct}%</span>
          </div>
          <input
            id="drop"
            type="range"
            min={1}
            max={20}
            value={s.dropPct}
            aria-describedby="drop-help"
            onChange={(e) => update({ dropPct: Number(e.target.value) })}
          />
          <span id="drop-help" className="help">
            Sell after a {s.dropPct}% rebound from the buy price, or after {DIP_MAX_HOLD_DAYS} trading days
          </span>
        </div>
      )}

      {s.strategy === 'ride_the_hype' && (
        <div className="field">
          <div className="range-label">
            <label htmlFor="up-days">Buy after this many up days in a row</label>
            <span className="mono">{s.upDays}</span>
          </div>
          <input
            id="up-days"
            type="range"
            min={1}
            max={10}
            value={s.upDays}
            aria-describedby="up-days-help"
            onChange={(e) => update({ upDays: Number(e.target.value) })}
          />
          <span id="up-days-help" className="help">
            Sell after {s.upDays} down day{s.upDays === 1 ? '' : 's'} in a row
          </span>
        </div>
      )}

      {s.strategy === 'buy_and_hold' && <p className="help">Buys on the first day and never sells.</p>}

      <div className="field-row">
        <div className="field">
          <label htmlFor="start">Start date</label>
          <input
            id="start"
            type="text"
            inputMode="numeric"
            className="mono-input"
            value={s.start}
            placeholder="YYYY-MM-DD"
            aria-invalid={errors.start ? true : undefined}
            aria-describedby="start-help"
            onChange={(e) => update({ start: e.target.value.trim() })}
          />
          {errors.start ? (
            <FieldError id="start-help" message={errors.start} />
          ) : (
            <span id="start-help" className="help">
              Earliest: {EARLIEST_DATES.META} for META, {EARLIEST_DATES.PLTR} for PLTR
            </span>
          )}
        </div>
        <div className="field">
          <label htmlFor="amount">Starting amount</label>
          <input
            id="amount"
            type="text"
            inputMode="decimal"
            className="mono-input"
            value={s.amount}
            aria-invalid={errors.amount ? true : undefined}
            aria-describedby={errors.amount ? 'amount-error' : undefined}
            onChange={(e) => update({ amount: e.target.value })}
            onBlur={() => {
              const value = parseAmount(s.amount)
              if (Number.isFinite(value) && value > 0) update({ amount: formatAmountInput(value) })
            }}
          />
          {errors.amount && <FieldError id="amount-error" message={errors.amount} />}
        </div>
      </div>

      <div className="checkbox">
        <input id="compare" type="checkbox" checked={s.compare} onChange={(e) => update({ compare: e.target.checked })} />
        <label htmlFor="compare">Compare with buy-and-hold</label>
      </div>

      {errors.form && (
        <div className="notice notice-error" role="alert">
          <WarningIcon />
          {errors.form}
        </div>
      )}

      <button type="submit" className="button button-primary button-block" disabled={running}>
        {running ? (
          <>
            <SpinnerIcon /> Running…
          </>
        ) : (
          'Run backtest'
        )}
      </button>
      <span className="form-foot">Whole shares only · fee on every trade</span>
    </form>
  )
}

function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <span id={id} className="field-error">
      <WarningIcon size={14} />
      {message}
    </span>
  )
}

/* ---------------- Plain English (Claude agent) ---------------- */

const EXAMPLES = [
  'Buy Palantir after a 7% weekly drop',
  'Buy Meta after 3 up days in a row, sell after 3 down days',
  'Buy Meta when it falls 15% below its monthly high, hold at most 40 days',
]

type AgentState =
  | { kind: 'idle' }
  | { kind: 'running'; startedAt: number }
  | { kind: 'error'; message: string }
  | { kind: 'no-backtest'; result: RuleResponse }

function PlainEnglishForm() {
  const [prompt, setPrompt] = useState(EXAMPLES[0])
  const [state, setState] = useState<AgentState>({ kind: 'idle' })
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const running = state.kind === 'running'
  const trimmed = prompt.trim()

  useEffect(() => {
    if (state.kind !== 'running') return
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - state.startedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [state])

  useEffect(() => () => abortRef.current?.abort(), [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (running || trimmed.length < 3) return
    const controller = new AbortController()
    abortRef.current = controller
    setElapsed(0)
    setState({ kind: 'running', startedAt: Date.now() })
    try {
      const result = await runRule(trimmed, controller.signal)
      const id = finalBacktestId(result)
      if (id && !result.refused) {
        saveAgentRun(id, { prompt: trimmed, answer: result.answer, steps: result.steps })
        navigate(`/results/${id}`)
      } else {
        setState({ kind: 'no-backtest', result })
      }
    } catch (error) {
      if (controller.signal.aborted) {
        setState({ kind: 'idle' })
        return
      }
      setState({ kind: 'error', message: error instanceof ApiError ? error.message : 'Something went wrong. Try again.' })
    }
  }

  return (
    <form className="settings-form" onSubmit={submit} aria-label="Describe a rule" aria-busy={running}>
      <div className="field">
        <label htmlFor="rule">Describe your rule</label>
        <textarea
          id="rule"
          rows={4}
          value={prompt}
          maxLength={MAX_PROMPT_LENGTH}
          disabled={running}
          aria-describedby="rule-help"
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) e.currentTarget.form?.requestSubmit()
          }}
        />
        <span id="rule-help" className="help help-row">
          <span>Meta or Palantir only. Claude picks the closest strategy and runs it.</span>
          <span className="mono">
            {prompt.length}/{MAX_PROMPT_LENGTH}
          </span>
        </span>
      </div>

      <div className="examples" role="group" aria-label="Example rules">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="chip"
            disabled={running}
            aria-pressed={prompt === example}
            onClick={() => setPrompt(example)}
          >
            {example}
          </button>
        ))}
      </div>

      {running ? (
        <div className="button-pair">
          <button type="button" className="button button-running button-block" disabled>
            <SpinnerIcon /> Running…
          </button>
          <button type="button" className="button button-secondary" onClick={() => abortRef.current?.abort()}>
            Cancel
          </button>
        </div>
      ) : (
        <button type="submit" className="button button-primary button-block" disabled={trimmed.length < 3}>
          Run with Claude
        </button>
      )}

      <div aria-live="polite">
        {running && (
          <div className="notice" role="status">
            <SpinnerIcon />
            Claude is choosing a strategy and running backtests… {elapsed}s
          </div>
        )}
        {state.kind === 'error' && (
          <div className="notice notice-error" role="alert">
            <WarningIcon />
            {state.message}
          </div>
        )}
        {state.kind === 'no-backtest' && (
          <div className="inline-answer">
            <span className="section-label">{state.result.refused ? 'Claude declined' : 'Claude’s reply'}</span>
            <ClaudeAnswer text={state.result.answer} />
          </div>
        )}
      </div>
      <span className="form-foot">Uses the Claude API · whole shares · fee on every trade</span>
    </form>
  )
}
