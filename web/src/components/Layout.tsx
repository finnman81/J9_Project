import { Outlet, NavLink, useLocation, useParams } from 'react-router-dom'
import { useTheme } from '../themes/ThemeContext'

const SUBJECTS = ['reading', 'math'] as const
const PAGES = [
  { path: 'overview', label: 'Overview', caption: 'Executive view' },
  { path: 'student', label: 'Students', caption: 'Profiles and supports' },
  { path: 'grade-entry', label: 'Grade Entry', caption: 'Assessment workflow' },
  { path: 'analytics', label: 'Analytics', caption: 'Comparative insights' },
] as const

export function Layout() {
  const theme = useTheme()
  const { subject } = useParams<{ subject: string }>()
  const location = useLocation()
  const currentSubject = (subject ?? 'reading').toLowerCase()
  const base = `/app/${currentSubject}`
  const currentPage = PAGES.find((page) =>
    location.pathname.includes(page.path === 'student' ? '/student' : `/${page.path}`)
  )

  // Preserve current page when switching Reading <-> Math.
  // Example: /app/reading/student/<uuid> -> /app/math/student/<uuid>
  const pathForSubject = (targetSubject: string) => {
    const parts = location.pathname.split('/').filter(Boolean) // ["app","reading","student","..."]
    if (parts.length < 2 || parts[0] !== 'app') return `/app/${targetSubject}/overview${location.search}`
    const rest = parts.slice(2) // everything after subject
    const suffix = rest.length > 0 ? rest.join('/') : 'overview'
    return `/app/${targetSubject}/${suffix}${location.search}`
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg-app)] p-4 md:p-5">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-[1500px] gap-5">
      <aside
        className={`hidden shrink-0 flex-col rounded-[28px] border md:flex ${theme.sidebarPattern ? theme.sidebarPattern : ''}`}
        style={{
          width: 280,
          backgroundColor: theme.palette.sidebarBg ?? 'var(--color-bg-surface)',
          color: 'var(--color-text-primary)',
          borderColor: 'rgba(201, 215, 232, 0.85)',
          boxShadow: '0 24px 56px rgba(20, 33, 61, 0.08)',
        }}
      >
        <div className="border-b px-5 pb-5 pt-6" style={{ borderColor: 'rgba(201, 215, 232, 0.85)' }}>
          <div className="flex items-start gap-3">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-2xl text-sm font-semibold text-white"
              style={{
                background: 'linear-gradient(135deg, var(--color-brand-primary), #7ca7f7)',
                boxShadow: '0 16px 32px rgba(41, 91, 167, 0.22)',
              }}
            >
              PI
            </div>
            <div className="min-w-0">
              <h1 className="text-base font-semibold leading-tight" style={{ fontFamily: 'var(--font-family)' }}>
                {theme.appTitle}
              </h1>
              <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                PowerSchool-aligned academic operations
              </p>
            </div>
          </div>
          <div
            className="mt-5 rounded-2xl border p-4"
            style={{
              borderColor: 'rgba(201, 215, 232, 0.85)',
              background: 'linear-gradient(180deg, rgba(234, 241, 255, 0.88), rgba(255, 255, 255, 0.96))',
            }}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
              District
            </p>
            <p className="mt-2 text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Peck Lower + Middle School
            </p>
            <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Spring benchmark readiness is live across Reading and Math.
            </p>
          </div>
        </div>
        <nav className="flex-1 px-4 py-5">
          <div
            className="mb-6 flex rounded-2xl border p-1"
            style={{ borderColor: 'rgba(201, 215, 232, 0.85)', backgroundColor: 'rgba(255, 255, 255, 0.78)' }}
          >
            {SUBJECTS.map((s) => (
              <NavLink
                key={s}
                to={pathForSubject(s)}
                className={({ isActive }) =>
                  `flex-1 rounded-xl px-3 py-2.5 text-center text-sm font-semibold ${
                    isActive ? 'text-white shadow-sm' : 'hover:bg-slate-50'
                  }`
                }
                style={({ isActive }) =>
                  isActive
                    ? {
                        background: 'linear-gradient(135deg, var(--color-brand-primary), #5d82d8)',
                      }
                    : { color: 'var(--color-text-secondary)' }
                }
              >
                {s === 'reading' ? 'Reading' : 'Math'}
              </NavLink>
            ))}
          </div>
          <div className="px-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
              Workspace
            </p>
          </div>
          <div className="mt-2 space-y-1.5">
            {PAGES.map((p) => (
              <NavLink
                key={p.path}
                to={p.path === 'student' ? `${base}/student` : `${base}/${p.path}`}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-2xl px-4 py-3.5 text-sm relative ${
                    isActive ? 'shadow-sm' : 'hover:bg-white'
                  }`
                }
                style={({ isActive }) =>
                  isActive
                    ? {
                        background: 'linear-gradient(180deg, rgba(234, 241, 255, 0.98), rgba(255, 255, 255, 0.96))',
                        border: '1px solid rgba(151, 180, 233, 0.65)',
                      }
                    : { border: '1px solid transparent', color: 'var(--color-text-secondary)' }
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className="h-10 w-10 shrink-0 rounded-2xl"
                      style={{
                        backgroundColor: isActive ? 'rgba(41, 91, 167, 0.12)' : 'rgba(233, 239, 248, 0.95)',
                        position: 'relative',
                      }}
                    >
                      <span
                        className="absolute left-1/2 top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                        style={{ backgroundColor: isActive ? 'var(--color-brand-primary)' : '#8ca2bf' }}
                      />
                    </span>
                    <span className="min-w-0">
                      <span
                        className="block truncate font-semibold"
                        style={{ color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}
                      >
                        {p.label}
                      </span>
                      <span className="block truncate text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        {p.caption}
                      </span>
                    </span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
          <div
            className="mt-6 rounded-3xl border p-4"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.82)',
              borderColor: 'rgba(201, 215, 232, 0.85)',
            }}
          >
            <p className="text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
              Data model
            </p>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span style={{ color: 'var(--color-text-secondary)' }}>Roster sync</span>
                <span className="rounded-full px-2 py-1 text-xs font-semibold" style={{ backgroundColor: 'var(--color-status-core-bg)', color: 'var(--color-status-core-text)' }}>
                  Healthy
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span style={{ color: 'var(--color-text-secondary)' }}>Interventions</span>
                <span className="rounded-full px-2 py-1 text-xs font-semibold" style={{ backgroundColor: 'var(--color-status-strategic-bg)', color: 'var(--color-status-strategic-text)' }}>
                  Monitor
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span style={{ color: 'var(--color-text-secondary)' }}>Benchmark window</span>
                <span className="rounded-full px-2 py-1 text-xs font-semibold" style={{ backgroundColor: 'var(--color-brand-primary-soft)', color: 'var(--color-brand-primary)' }}>
                  Active
                </span>
              </div>
            </div>
          </div>
        </nav>
      </aside>
      <main
        className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[32px] border bg-[var(--color-bg-surface)] text-[var(--color-text)]"
        style={{
          borderColor: 'rgba(201, 215, 232, 0.85)',
          boxShadow: '0 24px 56px rgba(20, 33, 61, 0.08)',
        }}
      >
        <header
          className="shrink-0 border-b px-6 py-5"
          style={{
            borderColor: 'rgba(201, 215, 232, 0.85)',
            background: 'linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(255, 255, 255, 0.96))',
          }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
                Student intelligence
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <h2 className="text-[1.5rem] font-semibold capitalize leading-tight" style={{ fontFamily: 'var(--font-family)' }}>
                  {currentPage?.label ?? (currentSubject === 'reading' ? 'Reading' : 'Math')}
                </h2>
                <span className="rounded-full px-3 py-1 text-xs font-semibold" style={{ backgroundColor: 'var(--color-brand-primary-soft)', color: 'var(--color-brand-primary)' }}>
                  {currentSubject === 'reading' ? 'Literacy program' : 'Math program'}
                </span>
              </div>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                PowerSchool structure with Schoolzilla-style decision support for campus teams.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border px-3 py-2 text-sm font-medium" style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: 'rgba(255, 255, 255, 0.88)' }}>
                Campus snapshot
              </span>
              <span className="rounded-full border px-3 py-2 text-sm font-medium" style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: 'rgba(255, 255, 255, 0.88)' }}>
                Spring 2025
              </span>
              <span className="rounded-full px-3 py-2 text-sm font-semibold text-white" style={{ background: 'linear-gradient(135deg, var(--color-brand-primary), #5d82d8)' }}>
                Live data
              </span>
            </div>
          </div>
        </header>
        <div className="flex-1 overflow-auto">
          <div className="mx-auto w-full px-5 py-5 md:px-6 md:py-6" style={{ maxWidth: 'var(--content-max-width)' }}>
            <Outlet />
          </div>
        </div>
      </main>
      </div>
    </div>
  )
}
