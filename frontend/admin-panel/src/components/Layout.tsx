import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const NAV = [
  { to: '/', label: '📊 Dashboard', end: true },
  { to: '/users', label: '👥 Users' },
  { to: '/cards', label: '🃏 Cards' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>⚔️ LotR TCG</h1>
          <span>Admin Panel</span>
        </div>
        <nav className="sidebar-nav">
          {NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-user">{user?.email}</div>
          <button
            className="btn-ghost btn-sm"
            style={{ width: '100%' }}
            onClick={signOut}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="main-content">
        {children}
      </main>
    </div>
  )
}
