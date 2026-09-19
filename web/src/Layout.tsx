import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './Auth'
import { BrandMark } from './ui/BrandMark'

export function Layout() {
  const { me, user, setLook, logout } = useAuth()
  const [navOpen, setNavOpen] = useState(false)
  const [themesOpen, setThemesOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setNavOpen(false)
    setThemesOpen(false)
    setAccountOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!endRef.current?.contains(e.target as Node)) {
        setThemesOpen(false)
        setAccountOpen(false)
      }
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [])

  const teacher = user?.is_teacher
  const theme = user?.theme || 'ascendancy'
  const density = user?.density || 'cozy'

  return (
    <div className="app-shell">
      <header className={`topbar ${navOpen ? 'is-nav-open' : ''}`} id="topbar">
        <div className="topbar__brand">
          <Link to={teacher ? '/teacher' : '/activities'} className="brand">
            <BrandMark />
            <span className="brand__words">
              <span className="brand__text">{me?.site_name || 'Ascendancy Academy'}</span>
              <span className="brand__tag">Ascend above the standards.</span>
            </span>
          </Link>
        </div>
        <button
          type="button"
          className="btn btn--ghost nav-toggle"
          aria-label={navOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={navOpen}
          onClick={() => setNavOpen((v) => !v)}
        >
          {navOpen ? 'Close' : 'Menu'}
        </button>
        <nav className="topnav" id="topnav">
          {teacher ? (
            <>
              <NavLink to="/teacher" className={({ isActive }) => (isActive ? 'is-current' : '')} end>
                Desk
              </NavLink>
              <NavLink to="/attendance" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Attendance
              </NavLink>
              <NavLink to="/courses" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Classes
              </NavLink>
              <NavLink to="/books" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Books
              </NavLink>
              <NavLink to="/calendar" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Calendar
              </NavLink>
              <NavLink to="/tasks" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                To-do
              </NavLink>
              <NavLink to="/notes" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Notes
              </NavLink>
              <NavLink to="/activities" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Activities
              </NavLink>
              <NavLink to="/tests" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Tests
              </NavLink>
              <NavLink to="/reminders" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Reminders
              </NavLink>
              <NavLink to="/documents" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Documents
              </NavLink>
              <NavLink to="/usage" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                AI Usage
              </NavLink>
              {user.can_manage_people ? (
                <NavLink to="/people" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                  People
                </NavLink>
              ) : null}
              {user.is_super_admin ? (
                <NavLink to="/admin" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                  Admin
                </NavLink>
              ) : null}
            </>
          ) : (
            <>
              <NavLink to="/activities" className={({ isActive }) => (isActive ? 'is-current' : '')} end>
                Activities
              </NavLink>
              <NavLink to="/attendance" className={({ isActive }) => (isActive ? 'is-current' : '')}>
                Attendance
              </NavLink>
            </>
          )}
        </nav>
        <div className="topbar__end" ref={endRef}>
          <div className="look-menu">
            <button type="button" className="btn btn--ghost" onClick={() => { setThemesOpen((v) => !v); setAccountOpen(false) }}>
              Themes
            </button>
            {themesOpen ? (
              <div className="look-menu__panel">
                <p className="look-menu__label">Colors</p>
                <div className="look-menu__row">
                  {(me?.themes || []).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`look-swatch ${theme === item ? 'is-on' : ''}`}
                      data-theme-preview={item}
                      onClick={() => void setLook(item, density)}
                    >
                      {me?.theme_labels?.[item] || item}
                    </button>
                  ))}
                </div>
                <p className="look-menu__label">Size</p>
                <div className="look-menu__row">
                  {(me?.densities || []).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`btn btn--small ${density === item ? 'btn--primary' : ''}`}
                      onClick={() => void setLook(theme, item)}
                    >
                      {me?.density_labels?.[item] || item}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
          <div className="account-menu">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => { setAccountOpen((v) => !v); setThemesOpen(false) }}
              aria-expanded={accountOpen}
            >
              {user?.nickname || user?.display_name || user?.first_name || 'Account'} ▾
            </button>
            {accountOpen ? (
              <div className="account-menu__panel">
                <Link to="/settings">Profile</Link>
                <Link to="/password">Change password</Link>
                <button
                  type="button"
                  onClick={() => {
                    void logout().then(() => navigate('/'))
                  }}
                >
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>
      <main className="main">
        {me?.school_year ? <p className="year-chip">{me.school_year}</p> : null}
        <Outlet />
      </main>
    </div>
  )
}
