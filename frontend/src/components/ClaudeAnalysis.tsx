import { Fragment, type ReactNode } from 'react'
import type { AgentStep } from '../api/agent'
import type { AgentRun } from '../lib/agentRuns'
import { CheckIcon, WarningIcon } from './Icons'

/** The Results screen's "Analysis · written by Claude" card. */
export function ClaudeAnalysis({ run }: { run?: AgentRun }) {
  return (
    <section aria-labelledby="analysis-heading" className="card analysis">
      <h2 id="analysis-heading" className="section-label">
        Analysis · written by Claude
      </h2>
      {run ? (
        <>
          <p className="analysis-prompt">
            You asked: <q>{run.prompt}</q>
          </p>
          <ClaudeAnswer text={run.answer} />
          <details className="tool-steps">
            <summary>
              How Claude got there · {run.steps.length} tool call{run.steps.length === 1 ? '' : 's'}
            </summary>
            <ol>
              {run.steps.map((step, i) => (
                <StepItem key={i} step={step} />
              ))}
            </ol>
          </details>
        </>
      ) : (
        <p className="muted">
          Claude writes an analysis when you describe your rule in plain English on the Backtest screen.
        </p>
      )}
    </section>
  )
}

// Claude writes short plain text: render paragraphs, "- " bullets and **bold** without injecting HTML.
export function ClaudeAnswer({ text }: { text: string }) {
  const bullet = /^\s*[-*•]\s+/
  const blocks = text.split(/\n\s*\n/).filter((block) => block.trim())
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

function StepItem({ step }: { step: AgentStep }) {
  const error = step.is_error ? (step.output as { error?: string } | null)?.error : undefined
  return (
    <li className="tool-step">
      <div className="tool-step-head">
        <span>{TOOL_LABELS[step.tool] ?? step.tool}</span>
        <span className={`status-word ${step.is_error ? 'is-bad' : 'is-ok'}`}>
          {step.is_error ? <WarningIcon size={14} /> : <CheckIcon size={14} />}
          {step.is_error ? 'Error' : 'OK'}
        </span>
      </div>
      {error && <p className="tool-step-error">{error}</p>}
      <details>
        <summary>
          <code>{step.tool}</code> input and output
        </summary>
        <pre>{JSON.stringify({ input: step.input, output: step.output }, null, 2)}</pre>
      </details>
    </li>
  )
}
