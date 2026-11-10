// Keeps Claude's analysis for a backtest in sessionStorage, so the Results screen can show it
// after navigation or a refresh. Storage can be unavailable (private mode), so failures are ignored.
import type { AgentStep } from '../api/agent'

export interface AgentRun {
  prompt: string
  answer: string
  steps: AgentStep[]
}

const key = (backtestId: string) => `agent-run:${backtestId}`

export function saveAgentRun(backtestId: string, run: AgentRun): void {
  try {
    sessionStorage.setItem(key(backtestId), JSON.stringify(run))
  } catch {
    // Not critical: the Results screen still works without Claude's analysis.
  }
}

export function loadAgentRun(backtestId: string): AgentRun | undefined {
  try {
    const raw = sessionStorage.getItem(key(backtestId))
    return raw ? (JSON.parse(raw) as AgentRun) : undefined
  } catch {
    return undefined
  }
}
