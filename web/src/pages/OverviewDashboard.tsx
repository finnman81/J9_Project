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

/** Grade order for charts and lists: Kindergarten → Eighth */
const GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth']

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
    const allYears = (filters?.school_years ?? []).filter((y) => y && y !== 'All')
    const selectedYear = !filter.school_year || filter.school_year === 'All' ? undefined : filter.school_year
    const defaultYear = allYears[0]
    const schoolYear = selectedYear
    return {
      teacher_name: filter.teacher_name === 'All' || !filter.teacher_name ? undefined : filter.teacher_name,
      // When no specific year is selected, omit school_year so metrics aggregate across years.
      school_year: schoolYear,
      subject: subjectParam,
      grade_level: filter.grade_level === 'All' || !filter.grade_level ? undefined : filter.grade_level,
      class_name: filter.class_name === 'All' || !filter.class_name ? undefined : filter.class_name,
      current_period: 'Fall',
      // For "This window" KPI, still use a concrete current_school_year even when aggregating.
      current_school_year: schoolYear ?? defaultYear ?? '2024-25',
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

  const distributionYMax = useMemo(() => {
    if (!histogramData.length) return 50
    const maxCount = Math.max(...histogramData.map((d) => d.count))
    return Math.ceil(Math.max(maxCount * 1.15, 10))
  }, [histogramData])

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
          <h1 className="text-left" style={{ fontSize: '1.75rem', fontWeight: 700, lineHeight: 1.25, fontFamily: 'var(--font-family)', color: '#1F2937' }}>
            {title}
          </h1>
          <p className="mt-2" style={{ fontSize: 'var(--context-line-size)', fontWeight: 'var(--context-line-weight)', color: '#64748B' }}>{filterSummary}</p>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0">
          {lastSynced && (
            <span style={{ fontSize: 'var(--muted-helper-size)', color: '#64748B' }}>
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
            style={{ backgroundColor: '#1E3A5F', fontSize: 'var(--button-text-size)', fontWeight: 600, boxShadow: '0 1px 3px rgba(30, 58, 95, 0.25)' }}
          >
            Add assessment
          </Link>
        </div>
      </header>

      {filters && (
        <div
          className="flex flex-wrap items-center gap-4 py-5 px-5 rounded-lg border"
          style={{ marginBottom: SECTION_GAP, backgroundColor: '#F8FAFC', borderColor: '#E2E8F0', boxShadow: 'none' }}
        >
          <input
            type="search"
            placeholder="Search student..."
            value={searchStudent}
            onChange={(e) => setSearchStudent(e.target.value)}
            className="w-44 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: '#CBD5E1', backgroundColor: '#fff' }}
          />
          <select
            className="w-32 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: '#CBD5E1', backgroundColor: '#fff' }}
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
            style={{ borderColor: '#CBD5E1', backgroundColor: '#fff' }}
            value={filter.class_name ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, class_name: e.target.value }))}
          >
            {filters.classes.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            className="w-40 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: '#CBD5E1', backgroundColor: '#fff' }}
            value={filter.teacher_name ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, teacher_name: e.target.value }))}
          >
            {filters.teachers.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select
            className="w-28 border rounded-[var(--radius-button)] px-3 h-10 text-[var(--body-size)]"
            style={{ borderColor: '#CBD5E1', backgroundColor: '#fff' }}
            value={filter.school_year ?? 'All'}
            onChange={(e) => setFilter((f) => ({ ...f, school_year: e.target.value }))}
          >
            {filters.school_years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <button type="button" onClick={resetFilters} className="px-3 py-2 rounded-[var(--radius-button)] h-10 bg-transparent border-0" style={{ color: '#1E3A5F', fontSize: 'var(--button-text-size)', fontWeight: 'var(--button-text-weight)' }}>
            Reset
          </button>
        </div>
      )}

      {/* Top KPI row: On Track / Monitor / Needs Support + Support Gap + Coverage by window + Tier movement */}
      <div style={{ marginBottom: SECTION_GAP }}>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-5">
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: kpiFilter === null ? '#93C5FD' : '#E2E8F0' }}>
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>Total Students</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{total}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0' }}>
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>Assessed</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.assessed_pct != null ? Number(kpis.assessed_pct).toFixed(1) : '0'}%</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{assessed} of {total}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0' }}>
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>Monitor</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.monitor_count ?? 0}</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{kpis?.monitor_pct != null ? Number(kpis.monitor_pct).toFixed(1) : '0'}%</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border-t-4 border bg-white text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0', borderTopColor: '#D97706' }}>
            <p className="text-[var(--label-size)] font-semibold" style={{ color: '#92400E' }}>Needs Support</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.needs_support_count ?? 0}</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{kpis?.needs_support_pct != null ? Number(kpis.needs_support_pct).toFixed(1) : '0'}%</p>
          </button>
          <button type="button" onClick={() => setKpiFilter('no_intervention')} className="min-h-[100px] flex flex-col justify-center rounded-lg border-t-4 border bg-white text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0', borderTopColor: kpiFilter === 'no_intervention' ? '#1E3A5F' : '#DC2626' }} title="Filter: Needs Support with no active intervention">
            <p className="text-[var(--label-size)] font-semibold" style={{ color: '#991B1B' }}>Support Gap</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.support_gap_count ?? 0}</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{kpis?.support_gap_pct != null ? Number(kpis.support_gap_pct).toFixed(1) : '0'}% · no intervention</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0' }}>
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>Intervention Coverage</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.intervention_coverage_pct != null ? Number(kpis.intervention_coverage_pct).toFixed(1) : '0'}%</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{kpis?.intervention_coverage_count ?? 0} of {kpis?.needs_support_count || 0}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0' }} title="% assessed in current window (e.g. Fall)">
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>% This window</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.assessed_this_window_pct != null ? Number(kpis.assessed_this_window_pct).toFixed(1) : '0'}%</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{kpis?.assessed_this_window_count ?? 0} of {total}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter('overdue')} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: kpiFilter === 'overdue' ? '#1E3A5F' : '#E2E8F0' }}>
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>Median Days Since</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.median_days_since_assessment != null ? Number(kpis.median_days_since_assessment).toFixed(1) : '—'}</p>
          </button>
          <button type="button" onClick={() => setKpiFilter('overdue')} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: kpiFilter === 'overdue' ? '#1E3A5F' : '#E2E8F0' }}>
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>% Overdue (&gt;90d)</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>{kpis?.overdue_pct != null ? Number(kpis.overdue_pct).toFixed(1) : '0'}%</p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>{kpis?.overdue_count ?? 0} students</p>
          </button>
          <button type="button" onClick={() => setKpiFilter(null)} className="min-h-[100px] flex flex-col justify-center rounded-lg border bg-[#F7F9FB] text-left" style={{ boxShadow: 'none', padding: 'var(--card-padding)', borderColor: '#E2E8F0' }} title="Tier movement (when tier history is populated)">
            <p className="text-[var(--label-size)] font-medium" style={{ color: '#64748B' }}>Tier movement</p>
            <p className="mt-2 font-bold" style={{ fontSize: '1.155em', color: '#1F2937' }}>
              {(kpis?.tier_moved_down_count ?? 0) > 0 || (kpis?.tier_moved_up_count ?? 0) > 0
                ? `↓${kpis?.tier_moved_down_count ?? 0} ↑${kpis?.tier_moved_up_count ?? 0}`
                : '—'}
            </p>
            <p className="text-[var(--caption-size)] mt-1" style={{ color: '#94A3B8' }}>Down better · Up worse</p>
          </button>
        </div>
      </div>

      {/* Priority Students (hero) */}
      <div style={{ marginBottom: SECTION_GAP }}>
        <div className="rounded-lg border overflow-hidden" style={{ boxShadow: 'none', backgroundColor: '#F7F9FB', borderColor: '#E2E8F0' }}>
          <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4 border-b" style={{ borderColor: '#E2E8F0' }}>
            <h2 className="font-semibold" style={{ fontSize: 'var(--section-title-size)', fontFamily: 'var(--font-family)', color: '#1F2937' }}>
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
              <thead className="sticky top-0 z-10 text-left" style={{ backgroundColor: '#E2E8F0', borderBottom: '2px solid #CBD5E1' }}>
                <tr>
                  <th className="font-semibold py-2.5 px-4" style={{ color: '#1F2937' }}>Name</th>
                  <th className="font-semibold py-2.5 px-4 text-center" style={{ color: '#1F2937' }}>Support Status</th>
                  <th className="font-semibold py-2.5 px-4 text-center" style={{ color: '#1F2937' }}>Tier</th>
                  <th className="font-semibold py-2.5 px-4 text-center" style={{ color: '#1F2937' }}>Has intervention</th>
                  <th className="font-semibold py-2.5 px-4 text-center" style={{ color: '#1F2937' }}>Days since assessment</th>
                  <th className="font-semibold py-2.5 px-4 text-center" style={{ color: '#1F2937' }}>Trend</th>
                  <th className="font-semibold font-bold py-2.5 px-4 text-center" style={{ color: '#1F2937' }}>Priority score</th>
                  <th className="font-semibold py-2.5 px-4" style={{ color: '#1F2937' }}>Reasons</th>
                </tr>
              </thead>
              <tbody>
                {priorityRows.map((r) => (
                  <tr
                    key={r.enrollment_id}
                    className="tr-hover-bg transition-colors cursor-pointer"
                    style={{ borderBottom: '1px solid #E2E8F0' }}
                    onClick={() => {
                      if (r.student_uuid) {
                        navigate(`/app/${subject}/student/${r.student_uuid}`)
                      } else {
                        navigate(`/app/${subject}/enrollment/${r.enrollment_id}`)
                      }
                    }}
                  >
                    <td className="py-2 px-4">
                      <span className="font-semibold" style={{ fontSize: 'var(--table-name-size)', color: '#1E3A5F' }}>
                        {r.display_name}
                      </span>
                      {r.grade_level && <span className="ml-2 text-[var(--caption-size)]" style={{ color: '#94A3B8' }}>{r.grade_level}</span>}
                    </td>
                    <td className="py-2 px-4 text-center">
                      <span
                        className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                        style={
                          r.support_status === 'Needs Support' ? { backgroundColor: '#FEF3C7', color: '#92400E' } :
                          r.support_status === 'Monitor' ? { backgroundColor: '#E0F2FE', color: '#0369A1' } :
                          r.support_status === 'On Track' ? { backgroundColor: '#D1FAE5', color: '#065F46' } : { backgroundColor: '#F1F5F9', color: '#475569' }
                        }
                      >
                        {r.support_status ?? 'Unknown'}
                      </span>
                    </td>
                    <td className="py-2 px-4 text-center">
                      <RiskBadge tier={tierToDisplayTier(r.tier)} showNotAssessed />
                    </td>
                    <td className="py-2 px-4 text-center">{r.has_active_intervention ? 'Yes' : 'No'}</td>
                    <td className="py-2 px-4 text-center">{r.days_since_assessment ?? '—'}</td>
                    <td className="py-2 px-4 text-center"><TrendChip trend={r.trend ?? undefined} /></td>
                    <td className="py-2 px-4 text-center font-bold" style={{ color: '#1F2937' }}>{r.priority_score != null ? Number(r.priority_score).toFixed(1) : '—'}</td>
                    <td className="py-2 px-4">
                      {r.reason_chips && r.reason_chips.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {r.reason_chips.map((chip) => (
                            <span key={chip} className="inline-block px-2 py-0.5 rounded text-xs" style={{ backgroundColor: '#FEF3C7', color: '#92400E', border: '1px solid #FDE68A' }}>
                              {chip}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[var(--caption-size)]" style={{ color: '#94A3B8' }}>{r.reasons ?? '—'}</span>
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
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">Median growth</p>
              <p className="text-3xl font-extrabold text-[var(--color-text)]">
                {growth?.median_growth != null ? Number(growth.median_growth).toFixed(1) : '—'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">score points</p>
            </div>
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">% Improving</p>
              <p className="text-3xl font-extrabold text-green-700">
                {growth?.pct_improving != null ? `${Number(growth.pct_improving).toFixed(1)}%` : '0%'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">since last period</p>
            </div>
            <button
              type="button"
              onClick={() => setKpiFilter('declining')}
              className="text-left"
              title="Filter priority table to declining trend"
            >
              <p className="text-[var(--label-size)] opacity-70 mb-1">% Declining</p>
              <p
                className={`text-3xl font-extrabold text-amber-700 ${
                  kpiFilter === 'declining' ? 'ring-2 ring-[var(--color-primary)] rounded px-1' : ''
                }`}
              >
                {growth?.pct_declining != null ? `${Number(growth.pct_declining).toFixed(1)}%` : '0%'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">click to filter table</p>
            </button>
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">Students w/ growth data</p>
              <p className="text-3xl font-extrabold text-[var(--color-text)]">
                {growth?.students_with_growth_data ?? 0}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">in current filters</p>
            </div>
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">% Stable</p>
              <p className="text-3xl font-extrabold text-sky-700">
                {growth?.pct_stable != null ? `${Number(growth.pct_stable).toFixed(1)}%` : '0%'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">little change between last two</p>
            </div>
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">Avg growth</p>
              <p className="text-3xl font-extrabold text-[var(--color-text)]">
                {growth?.avg_growth != null ? Number(growth.avg_growth).toFixed(1) : '—'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">mean change in score</p>
            </div>
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">Best gain</p>
              <p className="text-3xl font-extrabold text-emerald-700">
                {growth?.max_growth != null ? `+${Number(growth.max_growth).toFixed(1)}` : '—'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">top positive change</p>
            </div>
            <div>
              <p className="text-[var(--label-size)] opacity-70 mb-1">Largest drop</p>
              <p className="text-3xl font-extrabold text-red-700">
                {growth?.min_growth != null ? Number(growth.min_growth).toFixed(1) : '—'}
              </p>
              <p className="text-[var(--caption-size)] opacity-60 mt-1">most negative change</p>
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
                <BarChart data={histogramData} margin={{ top: 16, right: 16, left: 36, bottom: 36 }}>
                  <XAxis
                    dataKey="bin_min"
                    type="number"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v) => `${v}`}
                    label={{ value: 'Latest assessment score (0–100)', position: 'insideBottom', offset: -8, style: { textAnchor: 'middle', fontSize: 12 } }}
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    domain={[0, distributionYMax]}
                    label={{ value: 'Number of students', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 12 } }}
                  />
                  <Tooltip
                    formatter={(value: number, _name: string, props: { payload?: { count?: number; pct?: number } }) => {
                      const count = props.payload?.count ?? value
                      const pct = props.payload?.pct ?? 0
                      return [`${count} (${Number(pct).toFixed(1)}%)`, 'Count']
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
                <Tooltip formatter={(value: number, name: string) => [name === 'Avg Score' ? Number(value).toFixed(1) : `${Number(value).toFixed(1)}%`, name]} />
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
