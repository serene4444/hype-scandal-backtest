import { Fragment, type ReactNode, type Ref } from 'react'
import { latestOutput, type AgentStep, type MetricsOutput, type MonkeyOutput, type RuleResponse } from '../api/agent'
import {
  STRATEGY_LABELS,
  TICKER_LABELS,
  describeParams,
  formatDays,
  formatMoney,
  formatMoneyCents,
  formatPct,
} from '../lib/format'
import { CheckIcon, WarningIcon } from './Icons'

/** Beating at least this share of monkeys counts as evidence of skill (matches the agent's prompt). */
const SKILL_THRESHOLD = 0.95

interface Props {
  result: RuleResponse
  prompt: string
  headingRef?: Ref<HTMLHeadingElement>
}

export function RuleResult({ result, prompt, headingRef }: Props) {
  const metrics = latestOutput<MetricsOutput>(result.steps, 'get_metrics')
  const monkeys = metrics
    ? latestOutput<MonkeyOutput>(result.steps, 'compare_to_monkeys', metrics.backtest_id)
    : undefined

  return (
    <div className="result">
      <div className="result-title">
        <span className="label">{metrics ? interpretation(metrics) : 'Your rule'}</span>
        <h2 ref={headingRef} tabIndex={-1}>
          “{prompt}”
        </h2>
      </div>

      {result.refused && (
        <div className="notice notice-error" role="status">
          <WarningIcon />
          Claude declined this request, so no backtest was run.
        </div>
      )}

      {metrics && <Scorecard metrics={metrics} monkeys={monkeys} />}

      <div className="result-columns">
        <section aria-labelledby="analysis-heading" className="panel analysis">
          <h3 id="analysis-heading" className="label">
            Analysis · written by Claude
          </h3>
          <Answer text={result.answer} />
          {metrics && (
            <p className="fine-print">
              The scorecard comes straight from the backtester, not from Claude’s text. Backtest{' '}
              <code>{metrics.backtest_id.slice(0, 8)}</code>.
            </p>
          )}
        </section>

        <section aria-labelledby="steps-heading" className="panel steps">
          <h3 id="steps-heading" className="label">
            How Claude got there · {result.steps.length} tool call{result.steps.length === 1 ? '' : 's'}
          </h3>
          {result.steps.length === 0 ? (
            <p className="muted">Claude answered without calling any tools.</p>
          ) : (
            <ol className="step-list">
              {result.steps.map((step, index) => (
                <StepItem key={index} step={step} index={index} />
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  )
}

function interpretation(m: MetricsOutput): string {
  return [
    m.ticker,
    STRATEGY_LABELS[m.strategy] ?? m.strategy,
    ...describeParams(m.params),
    `${m.first_day} to ${m.last_day}`,
    formatMoney(m.amount),
  ].join(' · ')
}

function monkeyVerdict(share: number): string {
  if (share >= SKILL_THRESHOLD) return 'Strong sign of skill'
  if (share >= 0.5) return 'Could still be luck'
  return 'Worse than typical luck'
}

function Scorecard({ metrics, monkeys }: { metrics: MetricsOutput; monkeys?: MonkeyOutput }) {
  const s = metrics.strategy_metrics
  const hold = metrics.buy_and_hold_metrics
  const beatHold = metrics.beat_buy_and_hold
  return (
    <section aria-label="Scorecard" className="scorecard">
      <Tile label={`${formatMoney(metrics.amount)} became`} highlight>
        <span className="figure">{formatMoneyCents(s.ending_value)}</span>
        <span className="sub">
          {formatPct(s.total_return, true)} · buy-and-hold {formatMoneyCents(hold.ending_value)}
        </span>
      </Tile>
      <Tile label="Beat buy-and-hold?">
        <Verdict ok={beatHold} text={beatHold ? 'Yes' : 'No'} />
        <span className="sub">
          {beatHold ? 'Ahead' : 'Behind'} by {formatMoneyCents(Math.abs(metrics.ending_value_difference))}
        </span>
      </Tile>
      <Tile label="Beat the monkeys">
        {monkeys ? (
          <>
            <span className="figure">{formatPct(monkeys.share_beaten)}</span>
            <Verdict small ok={monkeys.share_beaten >= SKILL_THRESHOLD} text={monkeyVerdict(monkeys.share_beaten)} />
            <span className="sub">
              of {monkeys.n_monkeys.toLocaleString()} random traders · median {formatMoney(monkeys.median_ending_value)}
            </span>
          </>
        ) : (
          <span className="sub">Not compared</span>
        )}
      </Tile>
      <Tile label="Biggest drop">
        <span className="figure">{formatPct(s.max_drawdown)}</span>
        <span className="sub">Buy-and-hold {formatPct(hold.max_drawdown)}</span>
      </Tile>
      <Tile label="Trades · Sharpe">
        <span className="figure">
          {s.trade_count} · {s.sharpe.toFixed(2)}
        </span>
        <span className="sub">Recovery: {formatDays(s.time_to_recover).toLowerCase()}</span>
      </Tile>
    </section>
  )
}

function Tile({ label, highlight, children }: { label: string; highlight?: boolean; children: ReactNode }) {
  return (
    <div className={`tile${highlight ? ' tile-highlight' : ''}`}>
      <span className="label">{label}</span>
      {children}
    </div>
  )
}

function Verdict({ ok, text, small }: { ok: boolean; text: string; small?: boolean }) {
  return (
    <span className={`verdict ${ok ? 'is-ok' : 'is-bad'}${small ? ' verdict-small' : ''}`}>
      {ok ? <CheckIcon size={small ? 14 : 24} /> : <WarningIcon size={small ? 14 : 24} />}
      {text}
    </span>
  )
}

// Claude writes short plain text: render paragraphs, "- " bullets and **bold** without injecting HTML.
function Answer({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/).filter((block) => block.trim())
  const bullet = /^\s*[-*•]\s+/
  return (
    <div className="answer">
      {blocks.map((block, i) => {
        const lines = block.split('\n').filter((line) => line.trim())
        if (lines.every((line) => bullet.test(line))) {
          return (
            <ul key={i}>
              {lines.map((line, j) => (
                <li key={j}>{inline(line.replace(bullet, ''))}</li>
              ))}
            </ul>
          )
        }
        return <p key={i}>{inline(lines.join(' '))}</p>
      })}
    </div>
  )
}

function inline(text: string): ReactNode {
  return text
    .split(/\*\*(.+?)\*\*/g)
    .map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>))
}

const TOOL_LABELS: Record<string, string> = {
  list_strategies: 'Looked up stocks and rule templates',
  run_backtest: 'Ran the backtest',
  get_metrics: 'Scored it against buy-and-hold',
  compare_to_monkeys: 'Raced it against random monkeys',
}

function stepSummary(step: AgentStep): string | undefined {
  const out = (step.output ?? {}) as Record<string, unknown>
  if (step.is_error) return typeof out.error === 'string' ? out.error : 'Failed'
  const input = step.input
  switch (step.tool) {
    case 'run_backtest': {
      const ticker = String(input.ticker ?? '')
      const strategy = STRATEGY_LABELS[String(input.strategy)] ?? String(input.strategy ?? '')
      const params = describeParams(input.params as Record<string, unknown> | undefined)
      const ending = (out.metrics as { ending_value?: number } | undefined)?.ending_value
      return [
        TICKER_LABELS[ticker] ?? ticker,
        [strategy, ...params].join(', '),
        `from ${String(input.start_date ?? '')}`,
      ].join(' · ') + (ending !== undefined ? ` → ${formatMoneyCents(ending)}` : '')
    }
    case 'get_metrics':
      if (typeof out.beat_buy_and_hold !== 'boolean') return undefined
      return out.beat_buy_and_hold ? 'Beat buy-and-hold' : 'Did not beat buy-and-hold'
    case 'compare_to_monkeys':
      if (typeof out.share_beaten !== 'number') return undefined
      return `Beat ${formatPct(out.share_beaten)} of ${String(out.n_monkeys)} monkeys`
    default:
      return undefined
  }
}

function StepItem({ step, index }: { step: AgentStep; index: number }) {
  const summary = stepSummary(step)
  return (
    <li className={`step${step.is_error ? ' step-error' : ''}`}>
      <span className="step-number" aria-hidden="true">
        {String(index + 1).padStart(2, '0')}
      </span>
      <div className="step-body">
        <div className="step-head">
          <span className="step-title">{TOOL_LABELS[step.tool] ?? step.tool}</span>
          <span className={`verdict verdict-small ${step.is_error ? 'is-bad' : 'is-ok'}`}>
            {step.is_error ? <WarningIcon size={14} /> : <CheckIcon size={14} />}
            {step.is_error ? 'Error' : 'OK'}
          </span>
        </div>
        {summary && <p className="step-summary">{summary}</p>}
        <details>
          <summary>
            <code>{step.tool}</code> input and output
          </summary>
          <pre>{JSON.stringify({ input: step.input, output: step.output }, null, 2)}</pre>
        </details>
      </div>
    </li>
  )
}
