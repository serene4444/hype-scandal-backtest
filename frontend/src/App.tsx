import { useEffect } from 'react'
import { AppHeader } from './components/AppHeader'
import { Results } from './pages/Results'
import { RunBacktest } from './pages/RunBacktest'
import { navigate, useLocation } from './router'
import './App.css'

const TITLE = 'Hype vs. Scandal'

function App() {
  const { path } = useLocation()
  const resultsId = path.match(/^\/results\/([^/]+)\/?$/)?.[1]
  const isBacktest = path === '/backtest' || path === '/backtest/'

  useEffect(() => {
    // Welcome, login and dashboard come later; for now the app opens on Run a backtest.
    if (!resultsId && !isBacktest) navigate('/backtest', { replace: true })
  }, [resultsId, isBacktest])

  useEffect(() => {
    if (isBacktest) document.title = `Run a backtest · ${TITLE}`
  }, [isBacktest])

  return (
    <div className="app">
      <AppHeader current="backtest" />
      <main>{resultsId ? <Results key={resultsId} id={decodeURIComponent(resultsId)} /> : <RunBacktest />}</main>
    </div>
  )
}

export default App
