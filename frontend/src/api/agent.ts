// Client for POST /agent/rule: the plain-English rule builder.
// Shapes mirror backend/app/api/agent.py and the tool outputs in backend/app/agent/tools.py.

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

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

export interface Metrics {
  ending_value: number
  total_return: number
  max_drawdown: number
  time_to_recover: number | null
  sharpe: number
  trade_count: number
}

export interface MetricsOutput {
  backtest_id: string
  ticker: string
  strategy: string
  params: Record<string, number>
  first_day: string
  last_day: string
  trading_days: number
  amount: number
  fee: number
  strategy_metrics: Metrics
  buy_and_hold_metrics: Metrics
  beat_buy_and_hold: boolean
  ending_value_difference: number
}

export interface MonkeyOutput {
  backtest_id: string
  n_monkeys: number
  trade_count: number
  strategy_ending_value: number
  share_beaten: number
  median_ending_value: number
  p10_ending_value: number
  p90_ending_value: number
  best_ending_value: number
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string }
    if (first.msg) return first.msg
  }
  if (status === 504 || status === 502) return 'The server took too long or could not reach Claude. Try again.'
  return `Request failed (${status})`
}

export async function runRule(prompt: string, signal?: AbortSignal): Promise<RuleResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/agent/rule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Could not reach the backtester. Is the backend running?')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, body))
  return body as RuleResponse
}

/** Latest successful output of a tool, or undefined if it never succeeded. */
export function latestOutput<T>(steps: AgentStep[], tool: ToolName, backtestId?: string): T | undefined {
  for (let i = steps.length - 1; i >= 0; i--) {
    const step = steps[i]
    if (step.tool !== tool || step.is_error) continue
    const output = step.output as T & { backtest_id?: string }
    if (backtestId === undefined || output.backtest_id === backtestId) return output
  }
  return undefined
}
