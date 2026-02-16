import { Outlet, NavLink, useParams } from 'react-router-dom'
import { useTheme } from '../themes/ThemeContext'

const SUBJECTS = ['reading', 'math'] as const
const PAGES = [
  { path: 'overview', label: 'Overview' },
  { path: 'student', label: 'Student Detail' },
  { path: 'grade-entry', label: 'Grade Entry' },
  { path: 'analytics', label: 'Analytics' },
] as const

export function Layout() {
  const theme = useTheme()
  const { subject } = useParams<{ subject: string }>()
  const currentSubject = (subject ?? 'reading').toLowerCase()
  const base = `/app/${currentSubject}`

  return (
    <div className="flex min-h-screen">
      <aside
        className={`shrink-0 flex flex-col ${theme.sidebarPattern ? theme.sidebarPattern : ''}`}
        style={{
          width: 200,
          backgroundColor: theme.sidebarPattern ? undefined : (theme.palette.sidebarBg ?? theme.palette.primary),
          color: theme.palette.textOnPrimary,
        }}
      >
        <div className="px-4 py-5 border-b border-white/12">
          <h1 className="text-base font-semibold" style={{ fontFamily: 'var(--font-family)' }}>
            {theme.appTitle}
          </h1>
          <p className="text-xs opacity-85 mt-1">School Assessment System</p>
        </div>
        <nav className="flex-1 py-5 px-4">
          <div className="flex rounded-lg bg-white/10 p-0.5 mb-6">
            {SUBJECTS.map((s) => (
              <NavLink
                key={s}
                to={`/app/${s}/overview`}
                className={({ isActive }) =>
                  `flex-1 text-center py-2.5 rounded-md text-sm font-medium transition-colors ${
                    isActive ? 'bg-white/25 text-white' : 'text-white/80 hover:text-white hover:bg-white/10'
                  }`
                }
              >
                {s === 'reading' ? 'Reading' : 'Math'}
              </NavLink>
            ))}
          </div>
          <p className="text-[11px] uppercase tracking-wider text-white/60 px-2 mb-2">Pages</p>
          <div className="space-y-1">
            {PAGES.map((p) => (
              <NavLink
                key={p.path}
                to={p.path === 'student' ? `${base}/student` : `${base}/${p.path}`}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-3 rounded-md text-sm transition-colors relative ${
                    isActive ? 'bg-white/28 text-white font-semibold border-l-[3px] border-l-white -ml-px pl-[13px]' : 'text-white/90 hover:bg-white/10'
                  }`
                }
              >
                {p.label}
              </NavLink>
            ))}
          </div>
        </nav>
      </aside>
      <main className="flex-1 flex flex-col min-w-0 bg-[var(--color-surface)] text-[var(--color-text)]">
        <header className="h-12 shrink-0 border-b flex items-center px-6" style={{ borderColor: 'var(--color-border)' }}>
          <span className="font-medium capitalize text-[15px]" style={{ fontFamily: 'var(--font-family)' }}>
            {currentSubject === 'reading' ? 'Reading' : 'Math'}
          </span>
        </header>
        <div className="flex-1 overflow-auto">
          <div className="mx-auto w-full px-6 py-6" style={{ maxWidth: 'var(--content-max-width)' }}>
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  )
}
