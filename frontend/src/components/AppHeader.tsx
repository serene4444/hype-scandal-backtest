export function AppHeader() {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-name">Hype vs. Scandal</span>
        <span className="label">Strategy backtester</span>
      </div>
      <nav aria-label="Main" className="main-nav">
        {/* Dashboard, Backtest, Tournament and ML model join this nav as those screens are built. */}
        <a href="/" aria-current="page">
          Rule builder
        </a>
      </nav>
    </header>
  )
}
