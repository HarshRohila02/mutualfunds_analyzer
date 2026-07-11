import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import FundPage from './pages/FundPage'
import ManagersPage from './pages/ManagersPage'
import ResearchPage from './pages/ResearchPage'

export default function App() {
  return (
    <BrowserRouter>
      <header className="masthead">
        <NavLink to="/" className="wordmark">
          Kosh<span>.</span>
        </NavLink>
        <span className="tagline">Mutual fund research desk — India</span>
        <nav>
          <NavLink to="/" end>
            Funds
          </NavLink>
          <NavLink to="/managers">Managers</NavLink>
          <NavLink to="/research">Research</NavLink>
        </nav>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/fund/:code" element={<FundPage />} />
          <Route path="/managers" element={<ManagersPage />} />
          <Route path="/research" element={<ResearchPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
