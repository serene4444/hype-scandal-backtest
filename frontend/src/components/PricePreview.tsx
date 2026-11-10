import { useEffect, useState } from 'react'
import { EARLIEST_DATES, getPrices, type PricePoint } from '../api/backtests'
import { formatMoney } from '../lib/format'
import { useElementWidth } from '../lib/useElementWidth'

// Both stocks held from Palantir's first day, so the lines start from the same $1,000.
const SINCE = EARLIEST_DATES.PLTR
const H = 260
const PAD = { left: 16, right: 16, top: 52, bottom: 20 }
const META_STROKE = '#E6E8EB'
const PLTR_STROKE = '#8A9099'

type Series = { meta: PricePoint[]; pltr: PricePoint[] }

export function PricePreview() {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  const [series, setSeries] = useState<Series | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([getPrices('META', SINCE, controller.signal), getPrices('PLTR', SINCE, controller.signal)])
      .then(([meta, pltr]) => setSeries({ meta: meta.points, pltr: pltr.points }))
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [])

  const ready = series && series.meta.length > 1 && series.pltr.length > 1 && width > 0
  let content = null
  let metaEnd = 0
  let pltrEnd = 0

  if (ready) {
    const grow = (points: PricePoint[]) => points.map((p) => (1000 * p.close) / points[0].close)
    const meta = grow(series.meta)
    const pltr = grow(series.pltr)
    metaEnd = meta[meta.length - 1]
    pltrEnd = pltr[pltr.length - 1]
    const all = [...meta, ...pltr]
    const lo = Math.min(...all)
    const hi = Math.max(...all)
    const x = (i: number, len: number) => PAD.left + ((width - PAD.left - PAD.right) * i) / (len - 1)
    const y = (v: number) => H - PAD.bottom - ((v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom)
    const line = (values: number[]) => values.map((v, i) => `${x(i, values.length).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
    content = (
      <svg width={width} height={H} aria-hidden="true">
        <line x1={PAD.left} y1={y(1000)} x2={width - PAD.right} y2={y(1000)} stroke="#3A414B" strokeDasharray="4 4" />
        <polyline points={line(pltr)} fill="none" stroke={PLTR_STROKE} strokeWidth="2" strokeDasharray="6 5" />
        <polyline points={line(meta)} fill="none" stroke={META_STROKE} strokeWidth="2.5" />
      </svg>
    )
  }

  const label = ready
    ? `Price preview: $1,000 held since ${SINCE} became ${formatMoney(metaEnd)} in Meta and ${formatMoney(pltrEnd)} in Palantir.`
    : 'Price preview of Meta and Palantir'

  return (
    <div ref={ref} className="preview" role="img" aria-label={label}>
      {content}
      {ready ? (
        <div className="preview-key" aria-hidden="true">
          <span className="section-label">$1,000 held since {SINCE}</span>
          <span>
            <svg width="22" height="6">
              <line x1="0" y1="3" x2="22" y2="3" stroke={META_STROKE} strokeWidth="2" />
            </svg>
            META {formatMoney(metaEnd)}
          </span>
          <span>
            <svg width="22" height="6">
              <line x1="0" y1="3" x2="22" y2="3" stroke={PLTR_STROKE} strokeWidth="2" strokeDasharray="4 3" />
            </svg>
            PLTR {formatMoney(pltrEnd)}
          </span>
        </div>
      ) : (
        <span className="preview-pill" aria-hidden="true">
          {failed ? 'PRICE PREVIEW UNAVAILABLE' : 'PRICE PREVIEW · META vs PLTR'}
        </span>
      )}
    </div>
  )
}
