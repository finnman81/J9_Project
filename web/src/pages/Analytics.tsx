import { useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, type DistributionResponse } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

/** Grade order for charts and lists: Kindergarten → First → Second → Third → Fourth */
const GRADE_ORDER = ['Kindergarten', 'First', 'Second', 'Third', 'Fourth']

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
  const isMath = subject?.toLowerCase() === 'math'
  const subjectLabel = isMath ? 'Math' : 'Reading'
  const [distribution, setDistribution] = useState<DistributionResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getDistribution({ subject: subjectLabel })
      .then(setDistribution)
      .catch(() => setDistribution(null))
      .finally(() => setLoading(false))
  }, [subjectLabel])

  const avgByGradeOrdered = distribution?.avg_by_grade?.length
    ? sortByGrade(distribution.avg_by_grade)
    : []

  return (
    <div className="mx-auto" style={{ maxWidth: 'var(--content-max-width)' }}>
      <h1 className="text-2xl font-semibold mb-2" style={{ fontFamily: 'var(--font-family)' }}>
        {subjectLabel} Analytics
      </h1>
      <p className="text-[var(--context-line-size)] opacity-70 mb-8">
        Deeper analytics: norms, multi-year trends, and assessment-type breakdowns.
      </p>

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
                <Tooltip />
                <ReferenceLine y={70} stroke="#22c55e" strokeWidth={1.5} strokeDasharray="4 4" label={{ value: 'Benchmark 70', position: 'right', fontSize: 11 }} />
                <Bar dataKey="average_score" name="Avg Score (pts)" radius={[4, 4, 0, 0]} fill="var(--color-primary)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* ERB vs Independent Norm — placeholder until backend has norm_reference API */}
      <section className="mb-10 rounded border p-6 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
          ERB vs independent norm comparison
        </h2>
        <p className="text-[var(--caption-size)] opacity-70">
          Norm comparison table (our avg stanine, norm avg, diff) will appear here when <code className="bg-black/5 px-1 rounded">norm_reference</code> is populated and an analytics endpoint is added.
        </p>
      </section>

      {/* Multi-year support trend — placeholder */}
      <section className="mb-10 rounded border p-6 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
          Support need trends by year
        </h2>
        <p className="text-[var(--caption-size)] opacity-70">
          Multi-year trend lines (e.g. % needs support by school year) will appear here when a multi-year analytics endpoint is available.
        </p>
      </section>

      {/* Assessment type averages — placeholder */}
      <section className="mb-10 rounded border p-6 bg-[var(--color-bg-surface)]" style={{ borderColor: 'var(--color-border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
          Assessment type averages across school
        </h2>
        <p className="text-[var(--caption-size)] opacity-70">
          Averages by assessment type (e.g. Reading_Level, ERB Mathematics) will appear here when an assessment-type aggregate endpoint is added.
        </p>
      </section>
    </div>
  )
}
