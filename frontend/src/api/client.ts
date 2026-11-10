// Shared fetch wrapper for the FastAPI backend.

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  readonly status: number
  /** Form field the error belongs to (e.g. "start_date"), when the API says so. */
  readonly field?: string

  constructor(status: number, message: string, field?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.field = field
  }
}

const FIELD_PREFIX = /^(ticker|strategy|params|start_date|end_date|amount|fee|prompt):\s*(.+)$/s

function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail
  let message: string | undefined
  let field: string | undefined

  if (typeof detail === 'string') {
    message = detail
  } else if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: unknown[] }
    message = first.msg?.replace(/^Value error,\s*/, '')
    const loc = first.loc?.[first.loc.length - 1]
    if (typeof loc === 'string' && loc !== 'body') field = loc
  }

  const prefixed = message?.match(FIELD_PREFIX)
  if (prefixed) {
    field = prefixed[1]
    message = prefixed[2]
  }
  if (!message) {
    message =
      status === 502 || status === 504
        ? 'The server took too long or could not reach Claude. Try again.'
        : `Request failed (${status})`
  }
  return new ApiError(status, message, field)
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Could not reach the backtester. Is the backend running?')
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw toApiError(response.status, body)
  return body as T
}
