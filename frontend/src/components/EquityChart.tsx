import { useMemo, useState, type PointerEvent } from 'react'
import type { CurvePoint, Trade } from '../api/backtests'
import type { StockEvent } from '../lib/events'
import { formatMoney, formatMoneyCents } from '../lib/format'
import { useElementWidth } from '../lib/useElementWidth'

const RULE = '#FFFFFF'
const HOLD = '#6B727C'
const MARK = '#E6E8EB'
const GRID = '#1E232A'
const AXIS = '#2A3038'
const BASELINE = '#3A414B'
const LABEL = '#9BA1A9'

const H = 300
const LEFT = 76
const RIGHT_PAD = 12
const TOP = 16
const BOTTOM = 236
const YEAR_Y = 256
const EVENT_Y = 276

interface Props {
  curve: CurvePoint[]
  trades: Trade[]
  events: StockEvent[]
  amount: number
  showBuyAndHold: boolean
}

function niceTicks(lo: number, hi: number, count = 4): number[] {
  const raw = (hi - lo) / count
  if (!(raw > 0)) return []
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const norm = raw / magnitude
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * magnitude
  const ticks: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v)
  return ticks
}

export function EquityChart({ curve, trades, events, amount, showBuyAndHold }: Props) {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null)

  const W = Math.max(width, 300)
  const right = W - RIGHT_PAD
  const n = curve.length

  const geometry = useMemo(() => {
    const values = curve.flatMap((p) => (showBuyAndHold ? [p.strategy, p.buy_and_hold] : [p.strategy]))
    const min = Math.min(amount, ...values)
    const max = Math.max(amount, ...values)
    const pad = (max - min) * 0.05 || amount * 0.05
    const lo = Math.max(0, min - pad)
    const hi = max + pad
    const x = (i: number) => LEFT + ((right - LEFT) * i) / Math.max(n - 1, 1)
    const y = (v: number) => BOTTOM - ((v - lo) / (hi - lo)) * (BOTTOM - TOP)
    const indexOf = new Map(curve.map((p, i) => [p.date, i]))
    const line = (pick: (p: CurvePoint) => number) =>
      curve.map((p, i) => `${x(i).toFixed(1)},${y(pick(p)).toFixed(1)}`).join(' ')

    const years: { i: number; label: string }[] = []
    curve.forEach((p, i) => {
      const year = p.date.slice(0, 4)
      if (i === 0 || year !== curve[i - 1].date.slice(0, 4)) years.push({ i, label: year })
    })
    const yearGap = (right - LEFT) / Math.max(years.length, 1)
    const yearStride = yearGap < 44 ? Math.ceil(44 / yearGap) : 1

    const firstIndexOnOrAfter = (date: string) => curve.findIndex((p) => p.date >= date)
    const placedEvents = events
      .map((event) => ({ event, i: firstIndexOnOrAfter(event.date) }))
      .filter(({ event, i }) => n > 0 && i >= 0 && event.date >= curve[0].date)

    return {
      x,
      y,
      lo,
      hi,
      ticks: niceTicks(lo, hi).filter((t) => Math.abs(y(t) - y(amount)) > 14),
      rulePoints: line((p) => p.strategy),
      holdPoints: line((p) => p.buy_and_hold),
      trades: trades.flatMap((t) => {
        const i = indexOf.get(t.date)
        return i === undefined ? [] : [{ trade: t, i }]
      }),
      years: years.filter((_, k) => k % yearStride === 0),
      events: placedEvents,
    }
  }, [curve, trades, events, amount, showBuyAndHold, right, n])

  if (n === 0) return null
  const { x, y } = geometry
  const last = curve[n - 1]
  const hovered = hover === null ? null : curve[hover]
  const selected = geometry.events.find(({ event }) => event.date === selectedEvent)

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    const px = ((event.clientX - rect.left) / rect.width) * W
    const i = Math.round(((px - LEFT) / (right - LEFT)) * (n - 1))
    setHover(i >= 0 && i < n ? i : null)
  }

  const summary =
    `Portfolio value from ${formatMoney(amount)} to ${formatMoney(last.strategy)} between ${curve[0].date} and ${last.date}` +
    (showBuyAndHold ? `; buy-and-hold ended at ${formatMoney(last.buy_and_hold)}` : '') +
    `; ${trades.length} trades.`

  return (
    <section aria-labelledby="chart-heading" className="card chart-card">
      <div className="chart-head">
        <h2 id="chart-heading" className="section-label">
          Portfolio value
        </h2>
        <ul className="legend" aria-label="Chart key">
          <li>
            <svg width="24" height="6" aria-hidden="true">
              <line x1="0" y1="3" x2="24" y2="3" stroke={RULE} strokeWidth="2" />
            </svg>
            Your rule
          </li>
          {showBuyAndHold && (
            <li>
              <svg width="24" height="6" aria-hidden="true">
                <line x1="0" y1="3" x2="24" y2="3" stroke={HOLD} strokeWidth="2" strokeDasharray="4 3" />
              </svg>
              Buy-and-hold
            </li>
          )}
          <li>
            <svg width="10" height="10" aria-hidden="true">
              <polygon points="5,0 10,10 0,10" fill={MARK} />
            </svg>
            Buy
          </li>
          <li>
            <svg width="10" height="10" aria-hidden="true">
              <polygon points="0,0 10,0 5,10" fill={MARK} />
            </svg>
            Sell
          </li>
          {geometry.events.length > 0 && (
            <li>
              <svg width="10" height="10" aria-hidden="true">
                <rect x="1" y="1" width="8" height="8" fill="none" stroke={MARK} strokeWidth="1.5" />
              </svg>
              Event
            </li>
          )}
        </ul>
      </div>

      <p className="chart-readout" aria-hidden="true">
        {hovered ? (
          <>
            <span>{hovered.date}</span>
            <span>Your rule {formatMoneyCents(hovered.strategy)}</span>
            {showBuyAndHold && <span>Buy-and-hold {formatMoneyCents(hovered.buy_and_hold)}</span>}
          </>
        ) : (
          <span>Point at the chart to read values</span>
        )}
      </p>

      <div ref={ref} className="chart-frame">
        {width > 0 && (
          <svg
            width={W}
            height={H}
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={summary}
            onPointerMove={onPointerMove}
            onPointerLeave={() => setHover(null)}
          >
            {geometry.ticks.map((t) => (
              <g key={t}>
                <line x1={LEFT} y1={y(t)} x2={right} y2={y(t)} stroke={GRID} />
                <text x={LEFT - 8} y={y(t) + 4} textAnchor="end" className="chart-text" fill={LABEL}>
                  {formatMoney(t)}
                </text>
              </g>
            ))}
            <line x1={LEFT} y1={y(amount)} x2={right} y2={y(amount)} stroke={BASELINE} strokeDasharray="4 4" />
            <text x={LEFT - 8} y={y(amount) + 4} textAnchor="end" className="chart-text" fill={LABEL}>
              {formatMoney(amount)}
            </text>
            <line x1={LEFT} y1={BOTTOM} x2={right} y2={BOTTOM} stroke={AXIS} />
            {geometry.years.map(({ i, label }) => (
              <g key={label}>
                <line x1={x(i)} y1={BOTTOM} x2={x(i)} y2={BOTTOM + 5} stroke={AXIS} />
                <text x={x(i)} y={YEAR_Y} textAnchor="middle" className="chart-text" fill={LABEL}>
                  {label}
                </text>
              </g>
            ))}

            {selected && (
              <line
                x1={x(selected.i)}
                y1={TOP}
                x2={x(selected.i)}
                y2={EVENT_Y}
                stroke={MARK}
                strokeDasharray="1 4"
                strokeLinecap="round"
              />
            )}

            {showBuyAndHold && (
              <polyline points={geometry.holdPoints} fill="none" stroke={HOLD} strokeWidth="2" strokeDasharray="6 5" />
            )}
            <polyline points={geometry.rulePoints} fill="none" stroke={RULE} strokeWidth="2.5" strokeLinejoin="round" />

            {geometry.trades.map(({ trade, i }) => {
              const cx = x(i)
              const cy = y(curve[i].strategy)
              const points =
                trade.action === 'BUY'
                  ? `${cx},${cy + 5} ${cx + 5},${cy + 14} ${cx - 5},${cy + 14}`
                  : `${cx - 5},${cy - 14} ${cx + 5},${cy - 14} ${cx},${cy - 5}`
              return <polygon key={`${trade.date}-${trade.action}`} points={points} fill={MARK} />
            })}

            {geometry.events.map(({ event, i }) => (
              <rect
                key={event.date}
                x={x(i) - 5}
                y={EVENT_Y}
                width="10"
                height="10"
                fill={event.date === selectedEvent ? MARK : 'none'}
                stroke={MARK}
                strokeWidth="1.5"
              />
            ))}

            {hovered && hover !== null && (
              <g pointerEvents="none">
                <line x1={x(hover)} y1={TOP} x2={x(hover)} y2={BOTTOM} stroke={BASELINE} />
                {showBuyAndHold && <circle cx={x(hover)} cy={y(hovered.buy_and_hold)} r="3.5" fill={HOLD} />}
                <circle cx={x(hover)} cy={y(hovered.strategy)} r="4" fill={RULE} />
              </g>
            )}
          </svg>
        )}
      </div>

      {geometry.events.length > 0 && (
        <div className="events">
          <ul className="event-list" aria-label="Events">
            {geometry.events.map(({ event }) => (
              <li key={event.date}>
                <button
                  type="button"
                  className="event-button"
                  aria-pressed={event.date === selectedEvent}
                  onClick={() => setSelectedEvent(event.date === selectedEvent ? null : event.date)}
                >
                  <svg width="10" height="10" aria-hidden="true">
                    <rect
                      x="1"
                      y="1"
                      width="8"
                      height="8"
                      fill={event.date === selectedEvent ? MARK : 'none'}
                      stroke={MARK}
                      strokeWidth="1.5"
                    />
                  </svg>
                  {event.title}
                  <span className="event-date">{event.date}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="event-detail" aria-live="polite">
            {selected ? selected.event.detail : 'Select an event to see what happened.'}
          </p>
        </div>
      )}
    </section>
  )
}
