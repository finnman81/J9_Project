import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  api,
  type DistributionResponse,
  type GrowthMetricsResponse,
  type MetricsParams,
  type PriorityStudentsResponse,
  type TeacherKpisResponse,
} from '../api/client'
import { RiskBadge } from '../components/RiskBadge'
import { TrendChip } from '../components/TrendChip'

const SECTION_GAP = 'var(--section-gap)'
const GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth']
const PRIORITY_FILTER_LABEL: Record<Exclude<KpiFilter, null>, string> = {
  overdue: 'Only overdue students',
  declining: 'Only declining trends',
  no_intervention: 'Only support-gap students',
}

type KpiFilter = 'overdue' | 'declining' | 'no_intervention' | null

function sortByGrade<T extends { grade_level: string }>(rows: T[]): T[] {
  const order = new Map(GRADE_ORDER.map((g, i) => [g, i]))
  return [...rows].sort((a, b) => (order.get(a.grade_level) ?? 99) - (order.get(b.grade_level) ?? 99))
}

function tierToDisplayTier(tier: string): string {
  if (tier === 'Core') return 'Core (Tier 1)'
  if (tier === 'Strategic') return 'Strategic (Tier 2)'
  if (tier === 'Intensive') return 'Intensive (Tier 3)'
  return tier || 'Unknown'
}

function formatPct(value: number | null | undefined) {
  return `${Number(value ?? 0).toFixed(1)}%`
}

function formatValue(value: number | null | undefined, digits = 0) {
  if (value == null) return 'N/A'
  return Number(value).toFixed(digits)
}

function supportStatusTone(status?: string | null) {
  if (status === 'Needs Support') return { backgroundColor: '#FFF3E4', color: '#A8570C', borderColor: '#FFD6AE' }
  if (status === 'Monitor') return { backgroundColor: '#EAF1FF', color: '#295BA7', borderColor: '#C7D8FF' }
  if (status === 'On Track') return { backgroundColor: '#E8F7EE', color: '#17663D', borderColor: '#C8E8D4' }
  return { backgroundColor: '#F5F7FB', color: '#62748D', borderColor: '#D9E2EC' }
}

function SectionCard({
  title,
  subtitle,
  actions,
  children,
  className = '',
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-[28px] border bg-white ${className}`}
      style={{
        borderColor: 'rgba(201, 215, 232, 0.9)',
        boxShadow: 'var(--card-shadow)',
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4 border-b px-6 py-5" style={{ borderColor: 'rgba(217, 226, 236, 0.9)' }}>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
            Analytics block
          </p>
          <h2 className="mt-2 text-[1.2rem] font-semibold leading-tight" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h2>
          {subtitle && (
            <p className="mt-1.5 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {subtitle}
            </p>
          )}
        </div>
        {actions}
      </div>
      <div className="p-6">{children}</div>
    </section>
  )
}

function KpiCard({
  label,
  value,
  helper,
  accent,
  active = false,
  onClick,
}: {
  label: string
  value: string
  helper: string
  accent: string
  active?: boolean
  onClick?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group h-full min-w-0 overflow-hidden rounded-[24px] border p-5 text-left"
      style={{
        borderColor: active ? accent : 'rgba(201, 215, 232, 0.9)',
        background: active ? `linear-gradient(180deg, ${accent}12, #ffffff)` : 'linear-gradient(180deg, #fbfdff, #ffffff)',
        boxShadow: active ? '0 14px 28px rgba(41, 91, 167, 0.12)' : 'none',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
            {label}
          </p>
          <p
            className="mt-3 max-w-full overflow-hidden text-[clamp(1.5rem,2.2vw,1.875rem)] font-semibold leading-tight tracking-[-0.02em]"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {value}
          </p>
          <p className="mt-3 text-[13px] leading-5" style={{ color: 'var(--color-text-muted)' }}>
            {helper}
          </p>
        </div>
        <span
          className="h-11 w-11 shrink-0 rounded-2xl"
          style={{
            background: `linear-gradient(135deg, ${accent}20, ${accent}08)`,
            border: `1px solid ${accent}32`,
          }}
        />
      </div>
    </button>
  )
}

function ProgressRow({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  const safeValue = Math.max(0, Math.min(100, value))

  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span style={{ color: 'var(--color-text-secondary)' }}>{label}</span>
        <span className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          {formatPct(safeValue)}
        </span>
      </div>
      <div className="mt-2 h-2 rounded-full" style={{ backgroundColor: '#E8EEF6' }}>
        <div
          className="h-2 rounded-full"
          style={{
            width: `${safeValue}%`,
            background: `linear-gradient(90deg, ${color}, ${color}aa)`,
          }}
        />
      </div>
    </div>
  )
}

export function OverviewDashboard() {
  const { subject } = useParams<{ subject: string }>()
  const navigate = useNavigate()
  const isMath = subject?.toLowerCase() === 'math'
  const subjectKey = subject ?? 'reading'
  const subjectParam = isMath ? 'Math' : 'Reading'
  const subjectLabel = isMath ? 'Math' : 'Literacy'

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
      school_year: schoolYear,
      subject: subjectParam,
      grade_level: filter.grade_level === 'All' || !filter.grade_level ? undefined : filter.grade_level,
      class_name: filter.class_name === 'All' || !filter.class_name ? undefined : filter.class_name,
      current_period: 'Fall',
      current_school_year: schoolYear ?? defaultYear ?? '2024-25',
    }
  }, [filter, subjectParam, filters?.school_years])

  useEffect(() => {
    const ac = new AbortController()
    api.getDashboardFilters({ signal: ac.signal }).then(setFilters).catch(() => setFilters(null))
    return () => ac.abort()
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    const signal = ac.signal
    const run = async () => {
      setLoading(true)
      setError(null)
      const [k, p, g, d] = await Promise.all([
        api.getTeacherKpis(metricsParams, { signal }).catch(() => null),
        api.getPriorityStudents(metricsParams, { signal }).catch(() => null),
        api.getGrowthMetrics(metricsParams, { signal }).catch(() => null),
        api.getDistribution(metricsParams, { signal }).catch(() => null),
      ])

      if (signal.aborted) return

      setKpis(k ?? null)
      setPriority(p ?? null)
      setGrowth(g ?? null)
      setDistribution(d ?? null)
      setLastSynced(new Date())

      if (!k && !p) {
        setError('Metrics unavailable. Run migration_v3 and ensure student_enrollments exist.')
      }

      setLoading(false)
    }

    run().catch((err) => {
      if (err?.name === 'AbortError' || signal.aborted) return
      setError(err?.message ?? String(err))
      setKpis(null)
      setPriority(null)
      setGrowth(null)
      setDistribution(null)
      setLoading(false)
    })

    return () => ac.abort()
  }, [metricsParams])

  const resetFilters = () => {
    setFilter({})
    setKpiFilter(null)
    setSearchStudent('')
  }

  const defaultSchoolYear = useMemo(
    () => filters?.school_years?.find((year) => year && year !== 'All') ?? '2024-25',
    [filters?.school_years],
  )

  const filterSummary = useMemo(() => {
    const grade = !filter.grade_level || filter.grade_level === 'All' ? 'All grades' : filter.grade_level
    const className = !filter.class_name || filter.class_name === 'All' ? 'All classes' : filter.class_name
    const teacher = !filter.teacher_name || filter.teacher_name === 'All' ? 'All teachers' : filter.teacher_name
    const schoolYear = !filter.school_year || filter.school_year === 'All' ? defaultSchoolYear : filter.school_year
    return `${grade} / ${className} / ${teacher} / ${schoolYear}`
  }, [defaultSchoolYear, filter])

  const gradeOptions = useMemo(
    () =>
      [...(filters?.grade_levels ?? [])]
        .filter((grade) => grade && grade !== 'All')
        .sort((a, b) => (GRADE_ORDER.indexOf(a) === -1 ? 99 : GRADE_ORDER.indexOf(a)) - (GRADE_ORDER.indexOf(b) === -1 ? 99 : GRADE_ORDER.indexOf(b))),
    [filters?.grade_levels],
  )
  const classOptions = useMemo(() => (filters?.classes ?? []).filter((value) => value && value !== 'All'), [filters?.classes])
  const teacherOptions = useMemo(() => (filters?.teachers ?? []).filter((value) => value && value !== 'All'), [filters?.teachers])
  const schoolYearOptions = useMemo(() => (filters?.school_years ?? []).filter((value) => value && value !== 'All'), [filters?.school_years])

  const priorityRows = useMemo(() => {
    if (!priority?.rows) return []

    let list = [...priority.rows]

    if (searchStudent.trim()) {
      const query = searchStudent.trim().toLowerCase()
      list = list.filter((row) => row.display_name?.toLowerCase().includes(query))
    }

    if (kpiFilter === 'overdue') list = list.filter((row) => (row.days_since_assessment ?? 0) > 90)
    if (kpiFilter === 'declining') list = list.filter((row) => row.trend === 'Declining')
    if (kpiFilter === 'no_intervention') {
      list = list.filter((row) => !row.has_active_intervention && (row.tier === 'Intensive' || row.tier === 'Strategic'))
    }

    return list
  }, [kpiFilter, priority, searchStudent])

  const histogramData = useMemo(() => {
    if (!distribution?.bins?.length) return []
    return distribution.bins.map((bin) => ({
      range: `${bin.bin_min}-${bin.bin_max}`,
      count: bin.count,
      pct: bin.pct ?? 0,
      bin_min: bin.bin_min,
      bin_max: bin.bin_max,
    }))
  }, [distribution])

  const distributionYMax = useMemo(() => {
    if (!histogramData.length) return 50
    const maxCount = Math.max(...histogramData.map((row) => row.count))
    return Math.ceil(Math.max(maxCount * 1.15, 10))
  }, [histogramData])

  const total = kpis?.total_students ?? 0
  const assessed = kpis?.assessed_students ?? 0
  const supportGapCount = kpis?.support_gap_count ?? 0
  const needsSupportCount = kpis?.needs_support_count ?? 0
  const activePriorityLabel = kpiFilter ? PRIORITY_FILTER_LABEL[kpiFilter] : 'All flagged students'
  const heroTitle = `${subjectLabel} performance dashboard`

  const exportCsv = () => {
    if (!priorityRows.length) return

    const cols = ['display_name', 'grade_level', 'class_name', 'support_status', 'tier', 'has_active_intervention', 'days_since_assessment', 'trend', 'priority_score', 'reasons']
    const header = cols.join(',')
    const rows = priorityRows.map((row) =>
      cols
        .map((col) => {
          const value = (row as unknown as Record<string, unknown>)[col]
          const normalized = value == null ? '' : String(value)
          return normalized.includes(',') ? `"${normalized.replace(/"/g, '""')}"` : normalized
        })
        .join(','),
    )
    const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv;charset=utf-8' })
    const anchor = document.createElement('a')
    anchor.href = URL.createObjectURL(blob)
    anchor.download = `${subjectLabel.toLowerCase()}-priority-${new Date().toISOString().slice(0, 10)}.csv`
    anchor.click()
    URL.revokeObjectURL(anchor.href)
  }

  if (loading && !kpis && !priority) {
    return (
      <div className="flex items-center justify-center py-20 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        Loading dashboard...
      </div>
    )
  }

  if (error && !kpis && !priority) {
    return (
      <div className="max-w-xl rounded-[24px] border bg-[#FFF5F5] p-6" style={{ borderColor: '#F7C5D1', color: '#8A1C38' }}>
        <p className="text-lg font-semibold">Failed to load dashboard.</p>
        <p className="mt-2 text-sm">{error}</p>
        <p className="mt-3 text-sm">
          Ensure the API is running: <code className="rounded bg-white px-1.5 py-0.5">uvicorn api.main:app --reload --port 8000</code>
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto" style={{ maxWidth: 'var(--content-max-width)' }}>
      <section
        className="grid gap-5 xl:grid-cols-[1.45fr_0.95fr]"
        style={{ marginBottom: SECTION_GAP }}
      >
        <div
          className="rounded-[32px] border p-6 md:p-7"
          style={{
            borderColor: 'rgba(201, 215, 232, 0.9)',
            background:
              'linear-gradient(135deg, rgba(234, 241, 255, 0.95) 0%, rgba(255, 255, 255, 0.98) 48%, rgba(245, 248, 255, 0.96) 100%)',
            boxShadow: '0 24px 56px rgba(20, 33, 61, 0.08)',
          }}
        >
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="max-w-3xl">
              <h1
                className="text-[1.8rem] font-semibold leading-tight md:text-[2.3rem]"
                style={{ fontFamily: 'var(--font-family)', color: 'var(--color-text-primary)' }}
              >
                {heroTitle}
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={exportCsv}
                className="rounded-full border px-4 py-2.5 text-sm font-semibold"
                style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-primary)', backgroundColor: 'rgba(255, 255, 255, 0.88)' }}
              >
                Export roster
              </button>
              <Link
                to={`/app/${subjectKey}/grade-entry`}
                className="rounded-full px-4 py-2.5 text-sm font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, var(--color-brand-primary), #5d82d8)' }}
              >
                Add assessment
              </Link>
            </div>
          </div>

          <div className="mt-8 grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="min-w-0 rounded-[24px] border bg-white/80 p-5" style={{ borderColor: 'rgba(201, 215, 232, 0.8)' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Students in scope
                </p>
                <p className="mt-3 text-[clamp(1.5rem,2.3vw,1.95rem)] font-semibold leading-tight tracking-[-0.02em]" style={{ color: 'var(--color-text-primary)' }}>
                  {total}
                </p>
                <p className="mt-2 text-[13px] leading-5" style={{ color: 'var(--color-text-muted)' }}>
                  Current {subjectLabel.toLowerCase()} roster in selected context
                </p>
              </div>
              <div className="min-w-0 rounded-[24px] border bg-white/80 p-5" style={{ borderColor: 'rgba(201, 215, 232, 0.8)' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Assessed coverage
                </p>
                <p className="mt-3 text-[clamp(1.5rem,2.3vw,1.95rem)] font-semibold leading-tight tracking-[-0.02em]" style={{ color: 'var(--color-text-primary)' }}>
                  {formatPct(kpis?.assessed_pct)}
                </p>
                <p className="mt-2 text-[13px] leading-5" style={{ color: 'var(--color-text-muted)' }}>
                  {assessed} of {total} students have assessment history
                </p>
              </div>
              <div className="min-w-0 rounded-[24px] border bg-white/80 p-5" style={{ borderColor: 'rgba(201, 215, 232, 0.8)' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Support gap
                </p>
                <p className="mt-3 text-[clamp(1.5rem,2.3vw,1.95rem)] font-semibold leading-tight tracking-[-0.02em]" style={{ color: 'var(--color-text-primary)' }}>
                  {supportGapCount}
                </p>
                <p className="mt-2 text-[13px] leading-5" style={{ color: 'var(--color-text-muted)' }}>
                  Students flagged without an active intervention
                </p>
              </div>
            </div>

            <div
              className="rounded-[28px] border p-5"
              style={{
                borderColor: 'rgba(201, 215, 232, 0.8)',
                background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(242, 246, 255, 0.9))',
              }}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
                Model + UX direction
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {['PowerSchool data model', 'Schoolzilla workflows', 'Light visual polish'].map((pill) => (
                  <span
                    key={pill}
                    className="rounded-full px-3 py-1.5 text-xs font-semibold"
                    style={{ backgroundColor: 'var(--color-brand-primary-soft)', color: 'var(--color-brand-primary)' }}
                  >
                    {pill}
                  </span>
                ))}
              </div>
              <div className="mt-5 space-y-4">
                <div className="rounded-[22px] border bg-white px-4 py-3.5" style={{ borderColor: 'rgba(201, 215, 232, 0.8)' }}>
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Filter summary
                  </p>
                  <p className="mt-1.5 text-sm leading-6" style={{ color: 'var(--color-text-muted)' }}>
                    {filterSummary}
                  </p>
                </div>
                <div className="rounded-[22px] border bg-white px-4 py-3.5" style={{ borderColor: 'rgba(201, 215, 232, 0.8)' }}>
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Last sync
                  </p>
                  <p className="mt-1.5 text-sm leading-6" style={{ color: 'var(--color-text-muted)' }}>
                    {lastSynced ? lastSynced.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : 'Pending'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <SectionCard
          title="Operational signals"
          subtitle="Quick decisions that mirror student support workflows."
          actions={
            <button
              type="button"
              onClick={() => setKpiFilter(null)}
              className="rounded-full border px-3 py-2 text-sm font-semibold"
              style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: 'white' }}
            >
              Clear focus
            </button>
          }
        >
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => setKpiFilter('no_intervention')}
              className="w-full rounded-[24px] border p-4 text-left"
              style={{
                borderColor: kpiFilter === 'no_intervention' ? '#F3B455' : 'rgba(201, 215, 232, 0.9)',
                backgroundColor: kpiFilter === 'no_intervention' ? '#FFF7EC' : '#FBFDFF',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Intervention follow-through
                  </p>
                  <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Students needing support with no active intervention plan.
                  </p>
                </div>
                <span className="text-[1.65rem] font-semibold leading-none" style={{ color: '#A8570C' }}>
                  {supportGapCount}
                </span>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setKpiFilter('declining')}
              className="w-full rounded-[24px] border p-4 text-left"
              style={{
                borderColor: kpiFilter === 'declining' ? '#B23754' : 'rgba(201, 215, 232, 0.9)',
                backgroundColor: kpiFilter === 'declining' ? '#FFF3F6' : '#FBFDFF',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Growth watchlist
                  </p>
                  <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Students with declining trends since the last assessment window.
                  </p>
                </div>
                <span className="text-[1.65rem] font-semibold leading-none" style={{ color: '#B23754' }}>
                  {formatPct(growth?.pct_declining)}
                </span>
              </div>
            </button>
            <button
              type="button"
              onClick={() => setKpiFilter('overdue')}
              className="w-full rounded-[24px] border p-4 text-left"
              style={{
                borderColor: kpiFilter === 'overdue' ? '#295BA7' : 'rgba(201, 215, 232, 0.9)',
                backgroundColor: kpiFilter === 'overdue' ? '#EFF5FF' : '#FBFDFF',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Assessment freshness
                  </p>
                  <p className="mt-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    Median days since assessment plus the overdue roster slice.
                  </p>
                </div>
                <span className="text-[1.65rem] font-semibold leading-none" style={{ color: '#295BA7' }}>
                  {kpis?.overdue_count ?? 0}
                </span>
              </div>
            </button>
          </div>
        </SectionCard>
      </section>

      {filters && (
        <section
          className="rounded-[28px] border bg-white px-5 py-5 md:px-6"
          style={{
            marginBottom: SECTION_GAP,
            borderColor: 'rgba(201, 215, 232, 0.9)',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
                Query layer
              </p>
              <h2 className="mt-2 text-[1.15rem] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Filters tuned for PowerSchool-style roster pivots
              </h2>
            </div>
            {kpiFilter && (
              <button
                type="button"
                onClick={() => setKpiFilter(null)}
                className="rounded-full border px-3 py-2 text-sm font-semibold"
                style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-brand-primary)', backgroundColor: 'var(--color-brand-primary-soft)' }}
              >
                {activePriorityLabel}
              </button>
            )}
          </div>
          <div className="mt-5 grid gap-4 xl:grid-cols-[1.2fr_repeat(4,minmax(0,1fr))_auto]">
            <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
              Search student
              <input
                type="search"
                placeholder="Search by student name"
                value={searchStudent}
                onChange={(event) => setSearchStudent(event.target.value)}
                className="h-11 rounded-[16px] border px-4"
                style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
              />
            </label>
            <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
              Grade
              <select
                className="h-11 rounded-[16px] border px-4"
                style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
                value={filter.grade_level ?? 'All'}
                onChange={(event) => setFilter((current) => ({ ...current, grade_level: event.target.value }))}
              >
                <option value="All">All grades</option>
                {gradeOptions.map((grade) => (
                  <option key={grade} value={grade}>
                    {grade}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
              Class
              <select
                className="h-11 rounded-[16px] border px-4"
                style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
                value={filter.class_name ?? 'All'}
                onChange={(event) => setFilter((current) => ({ ...current, class_name: event.target.value }))}
              >
                <option value="All">All classes</option>
                {classOptions.map((className) => (
                  <option key={className} value={className}>
                    {className}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
              Teacher
              <select
                className="h-11 rounded-[16px] border px-4"
                style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
                value={filter.teacher_name ?? 'All'}
                onChange={(event) => setFilter((current) => ({ ...current, teacher_name: event.target.value }))}
              >
                <option value="All">All teachers</option>
                {teacherOptions.map((teacher) => (
                  <option key={teacher} value={teacher}>
                    {teacher}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
              School year
              <select
                className="h-11 rounded-[16px] border px-4"
                style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
                value={filter.school_year ?? 'All'}
                onChange={(event) => setFilter((current) => ({ ...current, school_year: event.target.value }))}
              >
                <option value="All">All years</option>
                {schoolYearOptions.map((schoolYear) => (
                  <option key={schoolYear} value={schoolYear}>
                    {schoolYear}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <button
                type="button"
                onClick={resetFilters}
                className="h-11 rounded-full border px-4 text-sm font-semibold"
                style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: '#FBFDFF' }}
              >
                Reset
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" style={{ marginBottom: SECTION_GAP }}>
        <KpiCard label="Students assessed" value={formatPct(kpis?.assessed_pct)} helper={`${assessed} of ${total} students with assessments`} accent="#295BA7" onClick={() => setKpiFilter(null)} />
        <KpiCard label="Needs support" value={String(needsSupportCount)} helper={`${formatPct(kpis?.needs_support_pct)} of active roster`} accent="#F3B455" onClick={() => setKpiFilter(null)} />
        <KpiCard label="Support gap" value={String(supportGapCount)} helper={`${formatPct(kpis?.support_gap_pct)} without active intervention`} accent="#B23754" active={kpiFilter === 'no_intervention'} onClick={() => setKpiFilter('no_intervention')} />
        <KpiCard label="Intervention coverage" value={formatPct(kpis?.intervention_coverage_pct)} helper={`${kpis?.intervention_coverage_count ?? 0} students actively served`} accent="#17663D" onClick={() => setKpiFilter(null)} />
        <KpiCard label="This window" value={formatPct(kpis?.assessed_this_window_pct)} helper={`${kpis?.assessed_this_window_count ?? 0} students assessed this term`} accent="#5D82D8" onClick={() => setKpiFilter(null)} />
        <KpiCard label="Median days since" value={formatValue(kpis?.median_days_since_assessment, 1)} helper="Assessment freshness across active roster" accent="#295BA7" active={kpiFilter === 'overdue'} onClick={() => setKpiFilter('overdue')} />
        <KpiCard label="Overdue > 90 days" value={formatPct(kpis?.overdue_pct)} helper={`${kpis?.overdue_count ?? 0} students need a new assessment`} accent="#295BA7" active={kpiFilter === 'overdue'} onClick={() => setKpiFilter('overdue')} />
        <KpiCard
          label="Tier movement"
          value={(kpis?.tier_moved_down_count ?? 0) > 0 || (kpis?.tier_moved_up_count ?? 0) > 0 ? `D${kpis?.tier_moved_down_count ?? 0} / U${kpis?.tier_moved_up_count ?? 0}` : 'N/A'}
          helper="Down means lower risk, up means higher risk"
          accent="#7A5AF8"
          onClick={() => setKpiFilter(null)}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.55fr_0.95fr]" style={{ marginBottom: SECTION_GAP }}>
        <SectionCard
          title="Priority students"
          subtitle={`${priorityRows.length} visible in the current roster slice. Click any row to jump into the student profile.`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ backgroundColor: '#FFF3E4', color: '#A8570C' }}>
                Intensive {priority?.flagged_intensive ?? 0}
              </span>
              <span className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ backgroundColor: '#EAF1FF', color: '#295BA7' }}>
                Strategic {priority?.flagged_strategic ?? 0}
              </span>
              <button
                type="button"
                onClick={exportCsv}
                className="rounded-full border px-3 py-2 text-sm font-semibold"
                style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: 'white' }}
              >
                Export
              </button>
            </div>
          }
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ backgroundColor: '#F5F7FB', color: 'var(--color-text-secondary)' }}>
                Focus: {activePriorityLabel}
              </span>
              <span className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ backgroundColor: '#F5F7FB', color: 'var(--color-text-secondary)' }}>
                Total flagged {priority?.total_flagged ?? 0}
              </span>
            </div>
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Ranked by support status, assessment recency, and growth trend.
            </p>
          </div>
          <div className="max-h-[620px] overflow-auto rounded-[24px] border" style={{ borderColor: 'rgba(217, 226, 236, 0.95)' }}>
            <table className="w-full min-w-[760px]" style={{ fontSize: 'var(--table-text-size)' }}>
              <thead className="sticky top-0 z-10" style={{ backgroundColor: 'var(--table-header-bg)' }}>
                <tr className="text-left">
                  <th className="px-4 py-3 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Student</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Support status</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Tier</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Intervention</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Days since</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Trend</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Priority</th>
                  <th className="px-4 py-3 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Reasons</th>
                </tr>
              </thead>
              <tbody>
                {priorityRows.map((row) => {
                  const statusTone = supportStatusTone(row.support_status)

                  return (
                    <tr
                      key={row.enrollment_id}
                      className="tr-hover-bg cursor-pointer align-top"
                      style={{ borderTop: '1px solid rgba(217, 226, 236, 0.9)' }}
                      onClick={() => {
                        if (row.student_uuid) {
                          navigate(`/app/${subjectKey}/student/${row.student_uuid}`)
                        } else {
                          navigate(`/app/${subjectKey}/enrollment/${row.enrollment_id}`)
                        }
                      }}
                    >
                      <td className="px-4 py-4">
                        <div className="flex flex-col gap-1">
                          <span className="font-semibold" style={{ color: 'var(--color-brand-primary)' }}>
                            {row.display_name}
                          </span>
                          <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                            {row.grade_level ?? 'No grade'}{row.class_name ? ` / ${row.class_name}` : ''}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span
                          className="inline-flex rounded-full border px-3 py-1.5 text-xs font-semibold"
                          style={statusTone}
                        >
                          {row.support_status ?? 'Unknown'}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-center">
                        <RiskBadge tier={tierToDisplayTier(row.tier)} showNotAssessed />
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span className="text-sm font-semibold" style={{ color: row.has_active_intervention ? '#17663D' : '#B23754' }}>
                          {row.has_active_intervention ? 'Active' : 'Missing'}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-center" style={{ color: 'var(--color-text-secondary)' }}>
                        {row.days_since_assessment ?? 'N/A'}
                      </td>
                      <td className="px-4 py-4 text-center">
                        <TrendChip trend={row.trend ?? undefined} />
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span
                          className="inline-flex rounded-full px-3 py-1.5 text-sm font-semibold"
                          style={{ backgroundColor: '#EFF5FF', color: '#295BA7' }}
                        >
                          {row.priority_score != null ? Number(row.priority_score).toFixed(1) : 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {row.reason_chips && row.reason_chips.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {row.reason_chips.map((chip) => (
                              <span
                                key={chip}
                                className="rounded-full border px-2.5 py-1 text-xs font-semibold"
                                style={{ borderColor: '#E3EAF5', backgroundColor: '#F7FAFF', color: 'var(--color-text-secondary)' }}
                              >
                                {chip}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                            {row.reasons ?? 'No reason supplied'}
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <div className="space-y-5">
          <SectionCard title="Cohort health" subtitle="Coverage and support posture at a glance.">
            <div className="space-y-5">
              <ProgressRow label="Students assessed" value={Number(kpis?.assessed_pct ?? 0)} color="#295BA7" />
              <ProgressRow label="Needs support" value={Number(kpis?.needs_support_pct ?? 0)} color="#F3B455" />
              <ProgressRow label="Intervention coverage" value={Number(kpis?.intervention_coverage_pct ?? 0)} color="#17663D" />
              <ProgressRow label="This window assessed" value={Number(kpis?.assessed_this_window_pct ?? 0)} color="#5D82D8" />
            </div>
          </SectionCard>

          <SectionCard title="Roster attention" subtitle="A compact operating list for weekly team meetings.">
            <div className="space-y-4">
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Flagged students
                  </p>
                  <span className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    {priority?.total_flagged ?? 0}
                  </span>
                </div>
                <p className="mt-1.5 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  {priority?.flagged_intensive ?? 0} intensive, {priority?.flagged_strategic ?? 0} strategic
                </p>
              </div>
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Growth data coverage
                  </p>
                  <span className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    {growth?.students_with_growth_data ?? 0}
                  </span>
                </div>
                <p className="mt-1.5 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Students with enough history for trend interpretation.
                </p>
              </div>
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    Active focus
                  </p>
                  <span className="text-sm font-semibold" style={{ color: 'var(--color-brand-primary)' }}>
                    {activePriorityLabel}
                  </span>
                </div>
                <p className="mt-1.5 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Useful for Schoolzilla-style team huddles and follow-up lists.
                </p>
              </div>
            </div>
          </SectionCard>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2" style={{ marginBottom: SECTION_GAP }}>
        <SectionCard title="Growth pulse" subtitle="Change over time for students with valid longitudinal data.">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Median growth
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: 'var(--color-text-primary)' }}>
                {formatValue(growth?.median_growth, 1)}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Score points
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Improving
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: '#17663D' }}>
                {formatPct(growth?.pct_improving)}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Students trending up
              </p>
            </div>
            <button
              type="button"
              onClick={() => setKpiFilter('declining')}
              className="rounded-[22px] border p-4 text-left"
              style={{
                borderColor: kpiFilter === 'declining' ? '#F6CAD3' : 'rgba(217, 226, 236, 0.95)',
                backgroundColor: kpiFilter === 'declining' ? '#FFF3F6' : '#FBFDFF',
              }}
            >
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Declining
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: '#B23754' }}>
                {formatPct(growth?.pct_declining)}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Click to focus the table
              </p>
            </button>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Stable
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: '#295BA7' }}>
                {formatPct(growth?.pct_stable)}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Low movement between windows
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Avg growth
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: 'var(--color-text-primary)' }}>
                {formatValue(growth?.avg_growth, 1)}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Mean change in score
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Best gain
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: '#17663D' }}>
                {growth?.max_growth != null ? `+${Number(growth.max_growth).toFixed(1)}` : 'N/A'}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Highest positive change
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Largest drop
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: '#B23754' }}>
                {formatValue(growth?.min_growth, 1)}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Most negative change
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.95)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Growth data
              </p>
              <p className="mt-3 text-[1.85rem] font-semibold leading-none" style={{ color: 'var(--color-text-primary)' }}>
                {growth?.students_with_growth_data ?? 0}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                Students with enough history
              </p>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Score distribution" subtitle="Latest assessment distribution with benchmark context.">
          {histogramData.length > 0 ? (
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={histogramData} margin={{ top: 12, right: 18, left: 18, bottom: 28 }}>
                  <XAxis
                    dataKey="bin_min"
                    type="number"
                    tick={{ fontSize: 12, fill: '#62748D' }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(value) => `${value}`}
                    label={{ value: 'Latest assessment score (0-100)', position: 'insideBottom', offset: -12, style: { textAnchor: 'middle', fontSize: 12, fill: '#62748D' } }}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: '#62748D' }}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, distributionYMax]}
                    label={{ value: 'Students', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 12, fill: '#62748D' } }}
                  />
                  <Tooltip
                    contentStyle={{ borderRadius: 16, borderColor: '#D9E2EC', boxShadow: '0 16px 32px rgba(20, 33, 61, 0.12)' }}
                    formatter={(value: number | string | undefined, _name?: string, props?: { payload?: { count?: number; pct?: number } }) => {
                      const count = props?.payload?.count ?? value
                      const pct = props?.payload?.pct ?? 0
                      return [`${count} students (${Number(pct).toFixed(1)}%)`, 'Count']
                    }}
                    labelFormatter={(label, payload) => {
                      const row = payload?.[0]?.payload as { bin_min?: number; bin_max?: number } | undefined
                      return row ? `Score ${row.bin_min}-${row.bin_max}` : String(label)
                    }}
                  />
                  {distribution?.support_threshold != null && (
                    <ReferenceLine x={distribution.support_threshold} stroke="#B23754" strokeWidth={1.5} strokeDasharray="5 5" label={{ value: 'Support', position: 'top', fontSize: 11, fill: '#B23754' }} />
                  )}
                  {distribution?.benchmark_threshold != null && (
                    <ReferenceLine x={distribution.benchmark_threshold} stroke="#17663D" strokeWidth={1.5} strokeDasharray="5 5" label={{ value: 'Benchmark', position: 'top', fontSize: 11, fill: '#17663D' }} />
                  )}
                  <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                    {histogramData.map((_, index) => (
                      <Cell key={index} fill={index % 2 === 0 ? '#295BA7' : '#7CA7F7'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              No score data available for the current filter set.
            </p>
          )}
        </SectionCard>
      </section>

      {distribution?.avg_by_grade && distribution.avg_by_grade.length > 0 && (
        <SectionCard
          title="Average score by grade"
          subtitle="Compares average score and the percentage of students needing support."
          className="overflow-hidden"
        >
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sortByGrade(distribution.avg_by_grade)} margin={{ top: 8, right: 20, left: 12, bottom: 20 }} barGap={8}>
                <XAxis dataKey="grade_level" tick={{ fontSize: 12, fill: '#62748D' }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" tick={{ fontSize: 12, fill: '#62748D' }} axisLine={false} tickLine={false} domain={[0, 105]} label={{ value: 'Score', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fontSize: 12, fill: '#62748D' } }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12, fill: '#62748D' }} axisLine={false} tickLine={false} domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
                <Tooltip
                  contentStyle={{ borderRadius: 16, borderColor: '#D9E2EC', boxShadow: '0 16px 32px rgba(20, 33, 61, 0.12)' }}
                  formatter={(value: number | string | undefined, name?: string) => [name === 'Avg score' ? Number(value ?? 0).toFixed(1) : `${Number(value ?? 0).toFixed(1)}%`, name ?? 'Value']}
                />
                <ReferenceLine yAxisId="left" y={70} stroke="#17663D" strokeWidth={1.5} strokeDasharray="5 5" />
                <Bar yAxisId="left" dataKey="average_score" name="Avg score" radius={[8, 8, 0, 0]} fill="#295BA7" />
                <Bar yAxisId="right" dataKey="pct_needs_support" name="% needs support" radius={[8, 8, 0, 0]} fill="#F3B455" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      )}
    </div>
  )
}
