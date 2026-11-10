import { Link } from './Link'
import { SettingsIcon } from './Icons'

/** Screens from the design that are not built yet; shown in the nav but not clickable. */
const COMING_SOON = ['Dashboard', 'Tournament', 'ML model']

export function AppHeader({ current }: { current: 'backtest' }) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-name">Hype vs. Scandal</span>
        <span className="brand-tag">Strategy backtester</span>
      </div>
      <nav aria-label="Main" className="main-nav">
        <span className="nav-soon" aria-disabled="true" title="Coming soon">
          {COMING_SOON[0]}
        </span>
        <Link to="/backtest" aria-current={current === 'backtest' ? 'page' : undefined}>
          Backtest
        </Link>
        {COMING_SOON.slice(1).map((name) => (
          <span key={name} className="nav-soon" aria-disabled="true" title="Coming soon">
            {name}
          </span>
        ))}
        <span className="nav-soon nav-icon" role="img" aria-label="Settings (coming soon)" title="Coming soon">
          <SettingsIcon />
        </span>
      </nav>
    </header>
  )
}
