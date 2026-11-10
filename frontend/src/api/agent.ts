// Client for POST /agent/rule: the plain-English rule builder.
// Shapes mirror backend/app/api/agent.py and the tool outputs in backend/app/agent/tools.py.
import type { Metrics } from './backtests'
import { request } from './client'

export const MAX_PROMPT_LENGTH = 500

export type ToolName = 'list_strategies' | 'run_backtest' | 'get_metrics' | 'compare_to_monkeys'

export interface AgentStep {
  tool: ToolName | string
  input: Record<string, unknown>
  output: unknown
  is_error: boolean
}

export interface RuleResponse {
  answer: string
  steps: AgentStep[]
  backtest_ids: string[]
  refused: boolean
}

export interface MetricsOutput {
  backtest_id: string
  ticker: string
  strategy: string
  params: Record<string, number>
  strategy_metrics: Metrics
  buy_and_hold_metrics: Metrics
  beat_buy_and_hold: boolean
}

export const runRule = (prompt: string, signal?: AbortSignal) =>
  request<RuleResponse>('/agent/rule', { method: 'POST', body: JSON.stringify({ prompt }), signal })

/** Latest successful output of a tool, or undefined if it never succeeded. */
export function latestOutput<T>(steps: AgentStep[], tool: ToolName): T | undefined {
  for (let i = steps.length - 1; i >= 0; i--) {
    if (steps[i].tool === tool && !steps[i].is_error) return steps[i].output as T
  }
  return undefined
}

/** The backtest Claude ended up scoring (falls back to the last one it ran). */
export function finalBacktestId(result: RuleResponse): string | undefined {
  return latestOutput<MetricsOutput>(result.steps, 'get_metrics')?.backtest_id ?? result.backtest_ids.at(-1)
}
