import { useParams } from 'react-router-dom'
import { useEffect, useState, useMemo } from 'react'
import {
  api,
  type DistributionResponse,
  type SupportTrendResponse,
  type AssessmentAveragesResponse,
  type ErbComparisonResponse,
  type MetricsParams,
} from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Line, CartesianGrid, Legend } from 'recharts'

/** Grade order for charts and lists: Kindergarten → Eighth */
const GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth']

function sortByGrade<T extends { grade_level: string }>(rows: T[]): T[] {
  const order = new Map(GRADE_ORDER.map((g, i) => [g, i]))
  return [...rows].sort((a, b) => (order.get(a.grade_level) ?? 99) - (order.get(b.grade_level) ?? 99))
}

/**
 * Analytics page: optional depth (ERB norm comparisons, multi-year trends, assessment type averages).
 * Hidden from default nav; linked from sidebar for admin/leadership.
 */
export function Analytics() {
  const { subject } = useParams<{ subject: string }>()
  const routeIsMath = subject?.toLowerCase() === 'math'
  const routeSubjectLabel = routeIsMath ? 'Math' : 'Reading'
  const [subjectFilter, setSubjectFilter] = useState<'Math' | 'Reading'>(routeSubjectLabel)
  const subjectLabel = subjectFilter
  const [distribution, setDistribution] = useState<DistributionResponse | null>(null)
  const [supportTrend, setSupportTrend] = useState<SupportTrendResponse | null>(null)
  const [assessmentAverages, setAssessmentAverages] = useState<AssessmentAveragesResponse | null>(null)
  const [erbComparison, setErbComparison] = useState<ErbComparisonResponse | null>(null)
  const [filters, setFilters] = useState<{ school_years: string[] } | null>(null)
  const [yearFilter, setYearFilter] = useState<string>('All')
  const [erbGradeFilter, setErbGradeFilter] = useState<string>('All')
  const [assessmentGradeFilter, setAssessmentGradeFilter] = useState<string>('All')
  const [loading, setLoading] = useState(true)

  // Load available school years for optional year filter (shared with dashboard)
  useEffect(() => {
    api
      .getDashboardFilters()
      .then((f) => setFilters({ school_years: f.school_years }))
      .catch(() => setFilters(null))
  }, [])

  const metricsParams: MetricsParams = useMemo(() => {
    const schoolYear =
      yearFilter === 'All' || !yearFilter ? undefined : yearFilter ?? filters?.school_years?.[0]
    return {
      subject: subjectLabel,
      school_year: schoolYear,
    }
  }, [subjectLabel, yearFilter, filters?.school_years])

  const assessmentAveragesParams = useMemo(
    () => ({
      ...metricsParams,
      grade_level: assessmentGradeFilter === 'All' ? undefined : assessmentGradeFilter,
    }),
    [metricsParams, assessmentGradeFilter],
  )

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getDistribution(metricsParams).catch(() => null),
      api.getSupportTrend(metricsParams).catch(() => null),
      api.getAssessmentAverages(assessmentAveragesParams).catch(() => null),
      api.getErbComparison(metricsParams).catch(() => null),
    ])
      .then(([dist, trend, averages, erb]) => {
        setDistribution(dist)
        setSupportTrend(trend)
        setAssessmentAverages(averages)
        setErbComparison(erb)
      })
      .finally(() => setLoading(false))
  }, [metricsParams.subject, metricsParams.school_year, assessmentGradeFilter])

  const avgByGradeOrdered = distribution?.avg_by_grade?.length ? sortByGrade(distribution.avg_by_grade) : []

  const supportTrendRows = supportTrend?.rows ?? []

  const assessmentAverageRows = useMemo(
    () => assessmentAverages?.rows?.filter((r) => r.average_score != null) ?? [],
    [assessmentAverages?.rows],
  )

  const erbRows = erbComparison?.rows ?? []
  const erbRowsFiltered =
    erbGradeFilter === 'All' ? erbRows : erbRows.filter((r) => r.grade_level === erbGradeFilter)

  return (
    <div className="mx-auto" style={{ maxWidth: 'var(--content-max-width)' }}>
      <h1 className="text-2xl font-semibold mb-2" style={{ fontFamily: 'var(--font-family)' }}>
        {subjectLabel} Analytics
      </h1>
      <p className="text-[var(--context-line-size)] opacity-70 mb-4">
        Deeper analytics: norms, multi-year trends, and assessment-type breakdowns.
      </p>

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="inline-flex rounded border bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
          <button
            type="button"
            className={`px-3 py-1.5 text-sm rounded-l ${subjectFilter === 'Reading' ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text)]'}`}
            onClick={() => setSubjectFilter('Reading')}
          >
            Reading
          </button>
          <button
            type="button"
            className={`px-3 py-1.5 text-sm rounded-r ${subjectFilter === 'Math' ? 'bg-[var(--color-primary)] text-white' : 'text-[var(--color-text)]'}`}
            onClick={() => setSubjectFilter('Math')}
          >
            Math
          </button>
        </div>
        {filters?.school_years && (
          <div className="flex items-center gap-2">
            <span className="text-sm opacity-80">School year:</span>
            <select
              className="border rounded px-2 py-1 text-sm"
              style={{ borderColor: 'var(--color-border)' }}
              value={yearFilter}
              onChange={(e) => setYearFilter(e.target.value)}
            >
              <option value="All">All years</option>
              {filters.school_years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loading && <p className="text-[var(--color-text)] opacity-70">Loading...</p>}

      {/* Avg by grade (context) */}
      {!loading && avgByGradeOrdered.length > 0 && (
        <section className="mb-10">
          <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
            Average score by grade
          </h2>
          <div className="h-72 rounded border p-4 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={avgByGradeOrdered} margin={{ top: 8, right: 8, left: 32, bottom: 24 }}>
                <XAxis dataKey="grade_level" tick={{ fontSize: 14 }} />
                <YAxis domain={[0, 105]} tick={{ fontSize: 14 }} label={{ value: 'Score (pts)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' } }} />
                <Tooltip formatter={(value: number) => [typeof value === 'number' ? Number(value).toFixed(1) : value, 'Avg Score (pts)']} />
                <ReferenceLine y={70} stroke="#22c55e" strokeWidth={1.5} strokeDasharray="4 4" label={{ value: 'Benchmark 70', position: 'right', fontSize: 11 }} />
                <Bar dataKey="average_score" name="Avg Score (pts)" radius={[4, 4, 0, 0]} fill="var(--color-primary)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* ERB vs Independent Norm */}
      <section className="mb-10 rounded border p-6 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-family)' }}>
            ERB vs independent norm comparison
          </h2>
          {erbRows.length > 0 && (
            <div className="flex items-center gap-2">
              <label htmlFor="erb-grade-filter" className="text-sm opacity-80">
                Grade:
              </label>
              <select
                id="erb-grade-filter"
                className="border rounded px-2 py-1.5 text-sm bg-[var(--color-bg-surface)]"
                style={{ borderColor: 'var(--color-border)', minWidth: '8rem' }}
                value={erbGradeFilter}
                onChange={(e) => setErbGradeFilter(e.target.value)}
              >
                <option value="All">All grades</option>
                {GRADE_ORDER.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        {erbRows.length === 0 ? (
          <p className="text-[var(--caption-size)] opacity-70">
            Norm comparison (our avg stanine vs independent norm) will appear here once ERB scores are entered for
            this subject.
          </p>
        ) : (() => {
          const byGrade: Record<string, { grade: string; our_stanine_total: number; ind_stanine_total: number; count: number }> = {}
          for (const r of erbRowsFiltered) {
            const g = r.grade_level
            if (!byGrade[g]) {
              byGrade[g] = { grade: g, our_stanine_total: 0, ind_stanine_total: 0, count: 0 }
            }
            byGrade[g].our_stanine_total += r.our_avg_stanine
            byGrade[g].ind_stanine_total += r.ind_avg_stanine
            byGrade[g].count += 1
          }
          const chartData = Object.values(byGrade)
            .map((g) => ({
              grade: g.grade,
              our_stanine: g.our_stanine_total / g.count,
              ind_stanine: g.ind_stanine_total / g.count,
            }))
            .sort((a, b) => GRADE_ORDER.indexOf(a.grade) - GRADE_ORDER.indexOf(b.grade))
          if (chartData.length === 0) {
            return (
              <p className="text-[var(--caption-size)] opacity-70">
                No ERB data for the selected grade. Choose &quot;All grades&quot; or another grade.
              </p>
            )
          }
          return (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  margin={{ top: 8, right: 24, left: 32, bottom: 32 }}
                  barGap={6}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="grade" tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    domain={[1, 9]}
                    label={{
                      value: 'Avg Stanine',
                      angle: -90,
                      position: 'insideLeft',
                      style: { textAnchor: 'middle', fontSize: 11 },
                    }}
                  />
                  <Tooltip formatter={(value: number) => [typeof value === 'number' ? Number(value).toFixed(1) : value]} />
                  <Legend />
                  <Bar dataKey="our_stanine" name="Our avg stanine" radius={[4, 4, 0, 0]} fill="var(--color-primary)" />
                  <Bar dataKey="ind_stanine" name="Independent norm" radius={[4, 4, 0, 0]} fill="#4b5563" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )
        })()}
      </section>

      {/* Multi-year support trend — placeholder */}
      <section className="mb-10 rounded border p-6 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
          Support need trends by year
        </h2>
        {supportTrendRows.length === 0 ? (
          <p className="text-[var(--caption-size)] opacity-70">
            Multi-year trend lines (e.g. % needs support by school year) will appear here once there is tier data in
            <code className="bg-black/5 px-1 ml-1 rounded">v_support_status</code>.
          </p>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={supportTrendRows} margin={{ top: 8, right: 16, left: 16, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="school_year" tick={{ fontSize: 12 }} />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 12 }}
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                  label={{
                    value: '% Needs Support',
                    angle: -90,
                    position: 'insideLeft',
                    style: { textAnchor: 'middle', fontSize: 11 },
                  }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 12 }}
                  tickFormatter={(v) => `${v}`}
                  label={{
                    value: 'Students',
                    angle: 90,
                    position: 'insideRight',
                    style: { textAnchor: 'middle', fontSize: 11 },
                  }}
                />
                <Tooltip formatter={(value: number, name: string) => [name === '% Needs Support' && typeof value === 'number' ? Number(value).toFixed(1) + '%' : value, name]} />
                <Legend />
                <Bar
                  yAxisId="left"
                  dataKey="pct_needs_support"
                  name="% Needs Support"
                  fill="#f59e0b"
                  radius={[4, 4, 0, 0]}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="needs_support"
                  name="Students needing support"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      {/* Assessment type averages */}
      <section className="mb-10 rounded border p-6 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-lg font-semibold" style={{ fontFamily: 'var(--font-family)' }}>
            Assessment type averages across school
          </h2>
          <div className="flex items-center gap-2">
            <label htmlFor="assessment-grade-filter" className="text-sm opacity-80">
              Grade:
            </label>
            <select
              id="assessment-grade-filter"
              className="border rounded px-2 py-1.5 text-sm bg-[var(--color-bg-surface)]"
              style={{ borderColor: 'var(--color-border)', minWidth: '8rem' }}
              value={assessmentGradeFilter}
              onChange={(e) => setAssessmentGradeFilter(e.target.value)}
            >
              <option value="All">All grades</option>
              {GRADE_ORDER.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </div>
        </div>
        {assessmentAverageRows.length === 0 ? (
          <p className="text-[var(--caption-size)] opacity-70">
            Averages by assessment type (e.g. Reading_Level, ERB Mathematics) will appear here once there are
            <code className="bg-black/5 px-1 ml-1 rounded">score_normalized</code> values for each assessment type.
          </p>
        ) : (
          <div style={{ height: Math.max(320, Math.min(600, assessmentAverageRows.length * 32)) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={assessmentAverageRows}
                margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
                barCategoryGap="8%"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 105]}
                  tick={{ fontSize: 12 }}
                  label={{
                    value: 'Avg Score (pts)',
                    position: 'insideBottom',
                    offset: -4,
                    style: { fontSize: 11 },
                  }}
                />
                <YAxis
                  type="category"
                  dataKey="assessment_type"
                  width={180}
                  tick={{ fontSize: 11 }}
                  interval={0}
                />
                <Tooltip formatter={(value: number) => [typeof value === 'number' ? Number(value).toFixed(1) : value, 'Avg Score']} />
                <Bar dataKey="average_score" name="Avg Score" radius={[0, 4, 4, 0]} fill="var(--color-primary)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>
    </div>
  )
}
