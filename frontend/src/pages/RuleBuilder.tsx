import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, MAX_PROMPT_LENGTH, runRule, type RuleResponse } from '../api/agent'
import { SpinnerIcon, WarningIcon } from '../components/Icons'
import { RuleResult } from '../components/RuleResult'

const EXAMPLES = [
  'Buy Palantir after a 7% weekly drop',
  'Buy Meta after 3 up days in a row and sell after 3 down days',
  'Buy Meta when it falls 15% below its monthly high, hold at most 40 days',
]

type State =
  | { kind: 'idle' }
  | { kind: 'running'; startedAt: number }
  | { kind: 'error'; message: string }
  | { kind: 'done'; prompt: string; result: RuleResponse }

export function RuleBuilder() {
  const [prompt, setPrompt] = useState(EXAMPLES[0])
  const [state, setState] = useState<State>({ kind: 'idle' })
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const resultHeadingRef = useRef<HTMLHeadingElement>(null)

  const running = state.kind === 'running'
  const trimmed = prompt.trim()
  const tooShort = trimmed.length < 3

  useEffect(() => {
    if (state.kind !== 'running') return
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - state.startedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [state])

  useEffect(() => {
    if (state.kind === 'done') resultHeadingRef.current?.focus()
  }, [state])

  useEffect(() => () => abortRef.current?.abort(), [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (running || tooShort) return
    const controller = new AbortController()
    abortRef.current = controller
    setElapsed(0)
    setState({ kind: 'running', startedAt: Date.now() })
    try {
      const result = await runRule(trimmed, controller.signal)
      setState({ kind: 'done', prompt: trimmed, result })
    } catch (error) {
      if (controller.signal.aborted) {
        setState({ kind: 'idle' })
        return
      }
      const message = error instanceof ApiError ? error.message : 'Something went wrong. Try again.'
      setState({ kind: 'error', message })
    } finally {
      if (abortRef.current === controller) abortRef.current = null
    }
  }

  return (
    <main className="page">
      <div className="page-title">
        <span className="label">AI rule builder · Claude with tool-calling</span>
        <h1>Describe a trading rule in plain English</h1>
        <p className="lede">
          Claude turns your rule into a backtest, then checks it against simply holding the stock and against 1,000
          random traders who make the same number of trades.
        </p>
      </div>

      <form className="panel rule-form" onSubmit={submit} aria-busy={running}>
        <label htmlFor="rule">Your rule</label>
        <textarea
          id="rule"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          maxLength={MAX_PROMPT_LENGTH}
          rows={3}
          disabled={running}
          aria-describedby="rule-help"
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) submit(event)
          }}
        />
        <div id="rule-help" className="field-help">
          <span>Meta or Palantir only. Starts with $1,000 and a $1 fee per trade unless you say otherwise.</span>
          <span className="mono">
            {prompt.length}/{MAX_PROMPT_LENGTH}
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

        <div className="form-actions">
          {running ? (
            <>
              <button type="button" className="button button-running" disabled>
                <SpinnerIcon />
                Running…
              </button>
              <button type="button" className="button button-secondary" onClick={() => abortRef.current?.abort()}>
                Cancel
              </button>
            </>
          ) : (
            <button type="submit" className="button button-primary" disabled={tooShort}>
              Test this rule
            </button>
          )}
        </div>

        <div aria-live="polite" className="form-status">
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
        </div>
      </form>

      {state.kind === 'done' && <RuleResult result={state.result} prompt={state.prompt} headingRef={resultHeadingRef} />}

      <p className="disclaimer">Educational simulation, not financial advice. No real money is traded.</p>
    </main>
  )
}
