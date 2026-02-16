import { useEffect, useState, useMemo } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  api,
  type MetricsParams,
  type TeacherKpisResponse,
  type PriorityStudentsResponse,
  type GrowthMetricsResponse,
  type DistributionResponse,
  type PriorityStudentRow,
} from '../api/client'
import { RiskBadge } from '../components/RiskBadge'
import { TrendChip } from '../components/TrendChip'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'

const SECTION_GAP = 'var(--section-gap)'

/** Grade order for charts and lists: Kindergarten → First → Second → Third → Fourth */
const GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth']

function sortByGrade<T extends { grade_level: string }>(rows: T[]): T[] {
  const order = new Map(GRADE_ORDER.map((g, i) => [g, i]))
  return [...rows].sort((a, b) => (order.get(a.grade_level) ?? 99) - (order.get(b.grade_level) ?? 99))
}

type KpiFilter = 'overdue' | 'declining' | 'no_intervention' | null

function tierToDisplayTier(tier: string): string {
  if (tier === 'Core') return 'Core (Tier 1)'
  if (tier === 'Strategic') return 'Strategic (Tier 2)'
  if (tier === 'Intensive') return 'Intensive (Tier 3)'
  return tier || 'Unknown'
}

export function OverviewDashboard() {
  const { subject } = useParams<{ subject: string }>()
  const navigate = useNavigate()
  const isMath = subject?.toLowerCase() === 'math'
  const subjectParam = isMath ? 'Math' : 'Reading'

  const [filter, setFilter] = useState<{ grade_level?: string; class_name?: string; teacher_name?: string; school_year?: string }>({})
  const [filters, setFilters] = useState<{ grade_levels: string[]; classes: string[]; teachers: string[]; school_years: string[] } | null>(null)
  const [kpis, setKpis] = useState<TeacherKpisResponse | null>(null)
  const [priority, setPriority] = useState<PriorityStudentsResponse | null>(null)
  const [growth, setGrowth] = useState<GrowthMetricsResponse | null>(null)
  const [distribution, setDistribution] = useState<DistributionResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [kpiFilter, setKpiFilter] = useState<KpiFilter>(null)
  const [searchStudent, setSearchStudent] = useState('')
  const [lastSynced, setLastSynced] = useState<Date | null>(null)

  const metricsParams: MetricsParams = useMemo(() => {
    const schoolYear = filter.school_year === 'All' || !filter.school_year ? undefined : filter.school_year
    return {
      teacher_name: filter.teacher_name === 'All' || !filter.teacher_name ? undefined : filter.teacher_name,
      school_year: schoolYear ?? filters?.school_years?.[0],
      subject: subjectParam,
      grade_level: filter.grade_level === 'All' || !filter.grade_level ? undefined : filter.grade_level,
      class_name: filter.class_name === 'All' || !filter.class_name ? undefined : filter.class_name,
      current_period: 'Fall',
      current_school_year: schoolYear ?? filters?.school_years?.[0] ?? '2024-25',
    }
  }, [filter, subjectParam, filters?.school_years])

  useEffect(() => {
    api.getDashboardFilters().then(setFilters).catch(() => setFilters(null))
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = metricsParams
    Promise.all([
      api.getTeacherKpis(params).catch(() => null),
      api.getPriorityStudents(params).catch(() => null),
      api.getGrowthMetrics(params).catch(() => null),
      api.getDistribution(params).catch(() => null),
    ])
      .then(([k, p, g, d]) => {
        setKpis(k ?? null)
        setPriority(p ?? null)
        setGrowth(g ?? null)
        setDistribution(d ?? null)
        setLastSynced(new Date())
        if (!k && !p) setError('Metrics unavailable. Run migration_v3 and ensure student_enrollments exist.')
      })
      .catch((err) => {
        setError(err?.message ?? String(err))
        setKpis(null)
        setPriority(null)
        setGrowth(null)
        setDistribution(null)
      })
      .finally(() => setLoading(false))
  }, [metricsParams.teacher_name, metricsParams.school_year, metricsParams.grade_level, metricsParams.class_name, metricsParams.current_period, metricsParams.current_school_year, subjectParam])

  const resetFilters = () => setFilter({})

  const filterSummary = useMemo(() => {
    const g = !filter.grade_level || filter.grade_level === 'All' ? 'All Grades' : filter.grade_level
    const c = !filter.class_name || filter.class_name === 'All' ? 'All Classes' : filter.class_name
    const t = !filter.teacher_name || filter.teacher_name === 'All' ? 'All Teachers' : filter.teacher_name
    const y = !filter.school_year || filter.school_year === 'All' ? (filters?.school_years?.[0] ?? '2024–25') : filter.school_year
    return `${g} • ${c} • ${t} • ${y}`
  }, [filter, filters])

  const priorityRows = useMemo(() => {
    if (!priority?.rows) return []
    let list = [...priority.rows]
    if (searchStudent.trim()) {
      const q = searchStudent.trim().toLowerCase()
      list = list.filter((r) => r.display_name?.toLowerCase().includes(q))
    }
    if (kpiFilter === 'overdue') list = list.filter((r) => (r.days_since_assessment ?? 0) > 90)
    if (kpiFilter === 'declining') list = list.filter((r) => r.trend === 'Declining')
    if (kpiFilter === 'no_intervention') list = list.filter((r) => !r.has_active_intervention && (r.tier === 'Intensive' || r.tier === 'Strategic'))
    return list
  }, [priority?.rows, searchStudent, kpiFilter])

  const histogramData = useMemo(() => {
    if (!distribution?.bins?.length) return []
    return distribution.bins.map((b) => ({
      range: `${b.bin_min}-${b.bin_max}`,
      count: b.count,
      pct: b.pct ?? 0,
      bin_min: b.bin_min,
      bin_max: b.bin_max,
    }))
  }, [distribution?.bins])

  const exportCsv = () => {
    if (!priorityRows.length) return
    const cols = ['display_name', 'grade_level', 'class_name', 'support_status', 'tier', 'has_active_intervention', 'days_since_assessment', 'trend', 'priority_score', 'reasons']
    const header = cols.join(',')
    const rows = priorityRows.map((r) =>
      cols.map((c) => {
        const v = (r as Record<string, unknown>)[c]
        const str = v == null ? '' : String(v)
        return str.includes(',') ? `"${str.replace(/"/g, '""')}"` : str
      }).join(',')
    )
    const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${isMath ? 'Math' : 'Literacy'}-priority-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const title = isMath ? 'Math Dashboard' : 'Literacy Dashboard'

  if (loading && !kpis && !priority) {
    return (
      <div className="flex items-center justify-center py-16 text-[var(--label-size)] text-[var(--color-text)] opacity-70">
        Loading...
      </div>
    )
  }
  if (error && !kpis && !priority) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-800 max-w-xl">
        <p className="font-semibold" style={{ fontSize: 'var(--section-title-size)' }}>Failed to load dashboard.</p>
        <p className="mt-2 text-[var(--label-size)]">{error}</p>
        <p className="mt-3 text-sm text-red-600">
          Ensure API is running: <code className="bg-red-100 px-1 rounded">uvicorn api.main:app --reload --port 8000</code>
        </p>
      </div>
    )
  }

  const total = kpis?.total_students ?? 0
  const assessed = kpis?.assessed_students ?? 0

  return (
    <div className="mx-auto" style={{ maxWidth: 'var(--content-max-width)' }}>
      <header className="flex flex-wrap items-start justify-between gap-6" style={{ marginBottom: SECTION_GAP }}>
        <div className="min-w-0">
          <h1 className="text-[var(--color-text)] text-left" style={{ fontSize: 'var(--page-title-size)', fontWeight: 'var(--page-title-weight)', lineHeight: 'var(--page-title-line-height)', fontFamily: 'var(--font-family)' }}>
            {title}
          </h1>
          <p className="mt-2 opacity-70" style={{ fontSize: 'var(--context-line-size)', fontWeight: 'var(--context-line-weight)' }}>{filterSummary}</p>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          {lastSynced && (
            <span className="text-[var(--color-text)] opacity-60" style={{ fontSize: 'var(--muted-helper-size)' }}>
              Last synced: {lastSynced.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
            </span>
          )}
          <button
            type="button"
            onClick={exportCsv}
            className="px-3 py-2 rounded-[var(--radius-button)] border transition-colors"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)', fontSize: 'var(--button-text-size)', fontWeight: 'var(--button-text-weight)' }}
          >
            Export
          </button>
          <Link
            to={`/app/${subject}/grade-entry`}
            className="px-3 py-2 rounded-[var(--radius-button)] text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: 'var(--color-primary)', fontSize: 'var(--button-text-size)', fontWeight: 'var(--button-text-weight)' }}
          >
            Add assessment
          </Link>
        </div>
      </header>

      {filters && (
        <div
          className="flex flex-wrap items-center gap-4 py-5 px-5 rounded-[var(--radius-card)] border border-[var(--color-border)]/40"
          style={{ marginBottom: SECTION_GAP, boxShadow: 'var(--card-shadow)', backgroundColor: 'var(--color-bg-surface-muted)' }}
        >
          <input
            type="search"
            placeholder="Search student..."
            value={searchStudent}
            onChange={(e) => setSearchStudent(e.target.value)}
            className="w-44 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: 'var(--color-border)' }}
          />
          <select
            className="w-32 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: 'var(--color-border)' }}
            value={filter.grade_level ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, grade_level: e.target.value }))}
          >
            <option value="">All Grades</option>
            {[...filters.grade_levels].sort((a, b) => {
              const ia = GRADE_ORDER.indexOf(a); const ib = GRADE_ORDER.indexOf(b)
              return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
            }).map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <select
            className="w-36 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: 'var(--color-border)' }}
            value={filter.class_name ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, class_name: e.target.value }))}
          >
            {filters.classes.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            className="w-40 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: 'var(--color-border)' }}
            value={filter.teacher_name ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, teacher_name: e.target.value }))}
          >
            {filters.teachers.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select
            className="w-28 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: 'var(--color-border)' }}
            value={filter.school_year ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, school_year: e.target.value }))}
          >
            {filters.school_years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <button type="button" onClick={resetFilters} className="px-3 py-2 rounded-[var(--radius-button)] border h-10" style={{ borderColor: 'var(--color-border)', color: 'var(--color-primary-accent)', fontSize: 'var(--button-text-size)', fontWeight: 'var(--button-text-weight)' }}>
            Reset
          </button>
        </div>
      )}

      {/* Top KPI row: On Track / Monitor / Needs Support + Support Gap + Coverage by window + Tier movement */}
      <div style={{ marginBottom: SECTION_GAP }}>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5">
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: kpiFilter === null ? 'var(--color-primary)' : 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-medium opacity-70">Total Students</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{total}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-medium opacity-70">Assessed</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{kpis?.assessed_pct ?? 0}%</p>
            <p className="text-[var(--caption-size)] opacity-60 mt-1">{assessed} of {total}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-medium opacity-70">Monitor</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{kpis?.monitor_count ?? 0}</p>
            <p className="text-[var(--caption-size)] opacity-60 mt-1">{kpis?.monitor_pct ?? 0}%</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border border-amber-300/60 bg-amber-50/90 text-left" style={{ boxShadow: 'var(--shadow-md)', padding: 'var(--kpi-card-padding)', borderColor: 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-bold text-amber-800/95">Needs Support</p>
            <p className="mt-2 font-bold text-amber-900" style={{ fontSize: 'var(--kpi-urgent-number-size)' }}>{kpis?.needs_support_count ?? 0}</p>
            <p className="text-[var(--caption-size)] text-amber-700/80 mt-1">{kpis?.needs_support_pct ?? 0}%</p>
          </button>
          <button type="button" onClick={() => setKpiFilter('no_intervention')} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border border-red-200 bg-red-50/90 text-left" style={{ boxShadow: 'var(--shadow-md)', padding: 'var(--kpi-card-padding)', borderColor: kpiFilter === 'no_intervention' ? 'var(--color-primary)' : undefined }} title="Filter: Needs Support with no active intervention">
            <p className="text-[var(--label-size)] font-bold text-red-800/95">Support Gap</p>
            <p className="mt-2 font-bold text-red-900" style={{ fontSize: 'var(--kpi-urgent-number-size)' }}>{kpis?.support_gap_count ?? 0}</p>
            <p className="text-[var(--caption-size)] text-red-700/80 mt-1">{kpis?.support_gap_pct ?? 0}% · no intervention</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-medium opacity-70">Intervention Coverage</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{kpis?.intervention_coverage_pct ?? 0}%</p>
            <p className="text-[var(--caption-size)] opacity-60 mt-1">{kpis?.intervention_coverage_count ?? 0} of {kpis?.needs_support_count || 0}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: 'var(--card-border)' }} title="% assessed in current window (e.g. Fall)">
            <p className="text-[var(--label-size)] font-medium opacity-70">% This window</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{kpis?.assessed_this_window_pct ?? 0}%</p>
            <p className="text-[var(--caption-size)] opacity-60 mt-1">{kpis?.assessed_this_window_count ?? 0} of {total}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter('overdue')} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: kpiFilter === 'overdue' ? 'var(--color-primary)' : 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-medium opacity-70">Median Days Since</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{kpis?.median_days_since_assessment != null ? Math.round(kpis.median_days_since_assessment) : '—'}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter('overdue')} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: kpiFilter === 'overdue' ? 'var(--color-primary)' : 'var(--card-border)' }}>
            <p className="text-[var(--label-size)] font-medium opacity-70">% Overdue (&gt;90d)</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>{kpis?.overdue_pct ?? 0}%</p>
            <p className="text-[var(--caption-size)] opacity-60 mt-1">{kpis?.overdue_count ?? 0} students</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-[var(--card-radius)] border bg-[var(--color-bg-surface-muted)] text-left" style={{ boxShadow: 'var(--card-shadow)', padding: 'var(--card-padding)', borderColor: 'var(--card-border)' }} title="Tier movement (when tier history is populated)">
            <p className="text-[var(--label-size)] font-medium opacity-70">Tier movement</p>
            <p className="mt-2 font-bold text-[var(--color-text)]" style={{ fontSize: 'var(--kpi-number-size)' }}>
              {(kpis?.tier_moved_down_count ?? 0) > 0 || (kpis?.tier_moved_up_count ?? 0) > 0
                ? `↓${kpis?.tier_moved_down_count ?? 0} ↑${kpis?.tier_moved_up_count ?? 0}`
                : '—'}
            </p>
            <p className="text-[var(--caption-size)] opacity-60 mt-1">Down better · Up worse</p>
          </button>
        </div>
      </div>

      {/* Priority Students (hero) */}
      <div style={{ marginBottom: SECTION_GAP }}>
        <div className="rounded-[var(--card-radius)] border overflow-hidden" style={{ boxShadow: 'var(--card-shadow)', backgroundColor: 'var(--color-bg-surface)', borderColor: 'var(--card-border)' }}>
          <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4 border-b" style={{ borderColor: 'var(--table-border)' }}>
            <h2 className="font-semibold text-[var(--color-text)]" style={{ fontSize: 'var(--section-title-size)', fontFamily: 'var(--font-family)' }}>
              Priority Students
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[var(--label-size)] opacity-70">
                Flagged Intensive: <strong>{priority?.flagged_intensive ?? 0}</strong>
              </span>
              <span className="text-[var(--label-size)] opacity-70">
                Flagged Strategic: <strong>{priority?.flagged_strategic ?? 0}</strong>
              </span>
              <span className="text-[var(--label-size)] opacity-70">
                Total Flagged: <strong>{priority?.total_flagged ?? 0}</strong>
              </span>
              <button type="button" onClick={exportCsv} className="px-3 py-1.5 rounded-[var(--radius-button)] border text-[var(--button-text-size)] font-medium" style={{ borderColor: 'var(--color-border)', color: 'var(--color-primary-accent)' }}>
                Export
              </button>
              <button type="button" disabled className="px-3 py-1.5 rounded-[var(--radius-button)] border border-gray-300 text-gray-400 cursor-not-allowed text-[var(--button-text-size)] font-medium">
                Assign intervention (coming soon)
              </button>
            </div>
          </div>
          <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
            <table className="w-full" style={{ fontSize: 'var(--table-text-size)' }}>
              <thead className="sticky top-0 z-10 text-left" style={{ backgroundColor: 'var(--table-header-bg)', borderBottom: '2px solid var(--table-border)' }}>
                <tr>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4">Name</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4 text-center">Support Status</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4 text-center">Tier</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4 text-center">Has intervention</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4 text-center">Days since assessment</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4 text-center">Trend</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4 text-center">Priority score</th>
                  <th className="font-semibold text-[var(--color-text)] py-3 px-4">Reasons</th>
                </tr>
              </thead>
              <tbody>
                {priorityRows.map((r) => (
                  <tr
                    key={r.enrollment_id}
                    className="tr-hover-bg transition-colors cursor-pointer"
                    style={{ borderBottom: '1px solid var(--table-border)' }}
                    onClick={() => navigate(`/app/${subject}/enrollment/${r.enrollment_id}`)}
                  >
                    <td className="py-3 px-4">
                      <span className="font-semibold text-[var(--color-primary-accent)]" style={{ fontSize: 'var(--table-name-size)' }}>
                        {r.display_name}
                      </span>
                      {r.grade_level && <span className="ml-2 opacity-60 text-[var(--caption-size)]">{r.grade_level}</span>}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          r.support_status === 'Needs Support' ? 'bg-amber-100 text-amber-800' :
                          r.support_status === 'Monitor' ? 'bg-sky-100 text-sky-800' :
                          r.support_status === 'On Track' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {r.support_status ?? 'Unknown'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <RiskBadge tier={tierToDisplayTier(r.tier)} showNotAssessed />
                    </td>
                    <td className="py-3 px-4 text-center">{r.has_active_intervention ? 'Yes' : 'No'}</td>
                    <td className="py-3 px-4 text-center">{r.days_since_assessment ?? '—'}</td>
                    <td className="py-3 px-4 text-center"><TrendChip trend={r.trend ?? undefined} /></td>
                    <td className="py-3 px-4 text-center font-medium">{r.priority_score ?? '—'}</td>
                    <td className="py-3 px-4">
                      {r.reason_chips && r.reason_chips.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {r.reason_chips.map((chip) => (
                            <span key={chip} className="inline-block px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-800 border border-amber-200">
                              {chip}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[var(--caption-size)] opacity-70">{r.reasons ?? '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Bottom: Growth metrics + Distribution + Avg by grade */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" style={{ marginBottom: SECTION_GAP }}>
        <div className="rounded-[var(--card-radius)] border p-5" style={{ boxShadow: 'var(--card-shadow)', backgroundColor: 'var(--color-bg-surface)', borderColor: 'var(--card-border)' }}>
          <h2 className="font-semibold text-[var(--color-text)] mb-4" style={{ fontSize: 'var(--section-title-size)', fontFamily: 'var(--font-family)' }}>
            Growth Metrics
          </h2>
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <p className="text-[var(--label-size)] opacity-70">Median growth</p>
              <p className="text-xl font-bold">{growth?.median_growth ?? '—'}</p>
            </div>
            <div>
              <p className="text-[var(--label-size)] opacity-70">% Improving</p>
              <p className="text-xl font-bold text-green-700">{growth?.pct_improving ?? 0}%</p>
            </div>
            <button
              type="button"
              onClick={() => setKpiFilter('declining')}
              className="text-left"
              title="Filter priority table to declining trend"
            >
              <p className="text-[var(--label-size)] opacity-70">% Declining</p>
              <p className={`text-xl font-bold text-amber-700 ${kpiFilter === 'declining' ? 'ring-2 ring-[var(--color-primary)] rounded px-1' : ''}`}>{growth?.pct_declining ?? 0}%</p>
            </button>
            <div>
              <p className="text-[var(--label-size)] opacity-70">Students w/ growth data</p>
              <p className="text-xl font-bold">{growth?.students_with_growth_data ?? 0}</p>
            </div>
          </div>
        </div>

        <div className="rounded-[var(--card-radius)] border p-5" style={{ boxShadow: 'var(--card-shadow)', backgroundColor: 'var(--color-bg-surface)', borderColor: 'var(--card-border)' }}>
          <h2 className="font-semibold text-[var(--color-text)] mb-4" style={{ fontSize: 'var(--section-title-size)', fontFamily: 'var(--font-family)' }}>
            Score distribution
          </h2>
          {histogramData.length > 0 ? (
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={histogramData} margin={{ top: 8, right: 8, left: 8, bottom: 24 }}>
                  <XAxis dataKey="bin_min" type="number" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}`} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    formatter={(value: number, _name: string, props: { payload?: { count?: number; pct?: number } }) => {
                      const count = props.payload?.count ?? value
                      const pct = props.payload?.pct ?? 0
                      return [`${count} (${pct}%)`, 'Count']
                    }}
                    labelFormatter={(label, payload) => {
                      const p = payload?.[0]?.payload as { bin_min?: number; bin_max?: number } | undefined
                      return p ? `Score ${p.bin_min}-${p.bin_max}` : String(label)
                    }}
                  />
                  {distribution?.support_threshold != null && (
                    <ReferenceLine x={distribution.support_threshold} stroke="#dc2626" strokeWidth={1.5} strokeDasharray="4 4" label={{ value: 'Support', position: 'top', fontSize: 10 }} />
                  )}
                  {distribution?.benchmark_threshold != null && (
                    <ReferenceLine x={distribution.benchmark_threshold} stroke="#16a34a" strokeWidth={1.5} strokeDasharray="4 4" label={{ value: 'Benchmark', position: 'top', fontSize: 10 }} />
                  )}
                  <Bar dataKey="count" name="Count" radius={[4, 4, 0, 0]}>
                    {histogramData.map((_, i) => (
                      <Cell key={i} fill="var(--color-primary)" />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-[var(--caption-size)] opacity-70">No score data for current filters.</p>
          )}
        </div>
      </div>

      {/* Recent changes (tier movement) — tier_history table populated by nightly job or on assessment entry */}
      <div className="rounded-[var(--card-radius)] border p-4 mb-6 bg-[var(--color-bg-surface-muted)]" style={{ borderColor: 'var(--color-border)' }}>
        <h2 className="font-semibold text-[var(--color-text)] mb-2" style={{ fontSize: 'var(--section-title-size)', fontFamily: 'var(--font-family)' }}>
          Tier movement
        </h2>
        <p className="text-[var(--caption-size)] opacity-70">
          Moved down (better): <strong>{kpis?.tier_moved_down_count ?? 0}</strong> · Moved up (worse): <strong>{kpis?.tier_moved_up_count ?? 0}</strong>.
          Once <code className="px-1 rounded bg-black/10">tier_history</code> is populated (on assessment entry or nightly job), these counts will show changes since last period.
        </p>
      </div>

      {distribution?.avg_by_grade && distribution.avg_by_grade.length > 0 && (
        <div className="rounded-[var(--card-radius)] border p-5" style={{ marginBottom: SECTION_GAP, boxShadow: 'var(--card-shadow)', backgroundColor: 'var(--color-bg-surface)', borderColor: 'var(--card-border)' }}>
          <h2 className="font-semibold text-[var(--color-text)] mb-4" style={{ fontSize: 'var(--section-title-size)', fontFamily: 'var(--font-family)' }}>
            Avg score by grade
          </h2>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sortByGrade(distribution.avg_by_grade)} margin={{ top: 8, right: 48, left: 32, bottom: 24 }} barCategoryGap="20%" barGap={8}>
                <XAxis dataKey="grade_level" tick={{ fontSize: 14 }} />
                <YAxis yAxisId="left" domain={[0, 105]} tick={{ fontSize: 14 }} label={{ value: 'Score (pts)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' } }} />
                <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(value: number, name: string) => [name === 'Avg Score' ? value : `${value}%`, name]} />
                <ReferenceLine yAxisId="left" y={70} stroke="#22c55e" strokeWidth={1.5} strokeDasharray="4 4" />
                <Bar yAxisId="left" dataKey="average_score" name="Avg Score" radius={[4, 4, 0, 0]} fill="var(--color-primary)" />
                <Bar yAxisId="right" dataKey="pct_needs_support" name="% Needs Support" radius={[4, 4, 0, 0]} fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
