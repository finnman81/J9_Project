import { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate, useLocation } from 'react-router-dom'
import {
  api,
  type Enrollment,
  type StudentDetailByUuidResponse,
  type Student,
  type Assessment,
  type Intervention,
} from '../api/client'
import { RiskBadge } from '../components/RiskBadge'
import { TrendChip } from '../components/TrendChip'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceArea } from 'recharts'

function tierToDisplayTier(tier: string | null): string {
  if (tier === 'Core') return 'Core (Tier 1)'
  if (tier === 'Strategic') return 'Strategic (Tier 2)'
  if (tier === 'Intensive') return 'Intensive (Tier 3)'
  return tier || 'Unknown'
}

export function StudentDetail() {
  const { subject, studentUuid: studentUuidParam, enrollmentId: enrollmentIdParam } = useParams<{
    subject: string
    studentUuid?: string
    enrollmentId?: string
  }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const idFromUrl = searchParams.get('id')
  const isMath = subject?.toLowerCase() === 'math'
  const subjectLabel = isMath ? 'Math' : 'Reading'

  // --- All enrollments (for the student picker) ---
  const [allEnrollments, setAllEnrollments] = useState<Enrollment[]>([])

  // --- UUID mode state ---
  const [uuidDetail, setUuidDetail] = useState<StudentDetailByUuidResponse | null>(null)
  // Empty array means "all enrollments selected" (no filter); non-empty = specific filter
  const [selectedEnrollmentIds, setSelectedEnrollmentIds] = useState<string[]>([])

  // --- Legacy student mode state ---
  const [students, setStudents] = useState<Student[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(idFromUrl ? parseInt(idFromUrl, 10) : null)
  const [student, setStudent] = useState<Student | null>(null)

  // --- Shared display state ---
  const [assessments, setAssessments] = useState<Assessment[]>([])
  const [interventions, setInterventions] = useState<Intervention[]>([])
  const [scoresHistory, setScoresHistory] = useState<{ period: string; score: number; assessment_type?: string }[]>([])
  const [header, setHeader] = useState<StudentDetailByUuidResponse['header'] | null>(null)
  const [notes, setNotes] = useState<Record<string, unknown>[]>([])
  const [goals, setGoals] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(false)
  // Single-select assessment type filter for the Score Over Time chart
  const [selectedAssessmentType, setSelectedAssessmentType] = useState<string>('')

  // Use UUID/enrollment flow whenever we're on the Student Detail route (with or without :studentUuid).
  // This ensures tier, trend, notes, and goals load from GET /api/student-detail/{uuid}?subject=Math.
  // Legacy mode (getStudents by id) only when explicitly on a route that has no /student in path (e.g. old bookmark).
  const isOnStudentPage = location.pathname.includes('/student')
  const isUuidMode = isOnStudentPage
  const isEnrollmentMode = Boolean(enrollmentIdParam) && !studentUuidParam
  const isLegacyMode = !isOnStudentPage

  // --- Derive unique students from all enrollments ---
  const uniqueStudents = (() => {
    const map = new Map<string, { displayName: string; studentUuid: string }>()
    for (const e of allEnrollments) {
      const key = e.student_uuid ?? e.display_name
      if (!map.has(key)) {
        map.set(key, { displayName: e.display_name, studentUuid: e.student_uuid ?? e.display_name })
      }
    }
    return Array.from(map.values())
  })()

  // --- Deduplicate legacy students ---
  const uniqueLegacyStudents = (() => {
    const map = new Map<string, Student>()
    for (const s of students) {
      const existing = map.get(s.student_name)
      if (!existing || s.school_year > existing.school_year) {
        map.set(s.student_name, s)
      }
    }
    return Array.from(map.values())
  })()

  // --- The enrollments belonging to the currently-viewed student (UUID mode) ---
  const studentEnrollments: Enrollment[] = uuidDetail?.enrollments ?? []

  // --- Load all enrollments for the student picker ---
  useEffect(() => {
    if (!isLegacyMode) {
      api.getEnrollments().then((r) => setAllEnrollments(r.enrollments))
    } else {
      api.getStudents().then((r) => setStudents(r.students))
    }
  }, [isLegacyMode])

  // --- UUID mode: Fetch data when studentUuid or selectedEnrollmentIds change ---
  const fetchUuidDetail = useCallback(
    (uuid: string, eids: string[]) => {
      setLoading(true)
      api
        .getStudentDetailByUuid(uuid, subjectLabel, eids.length > 0 ? eids : undefined)
        .then((d) => {
          setUuidDetail(d)
          setHeader(d.header)
          setAssessments(d.assessments)
          setInterventions(d.interventions)
          setScoresHistory(d.score_over_time)
          setNotes(d.notes)
          setGoals(d.goals)
        })
        .catch(() => {
          setUuidDetail(null)
          setHeader(null)
        })
        .finally(() => setLoading(false))
    },
    [subjectLabel],
  )

  useEffect(() => {
    if (isUuidMode && studentUuidParam) {
      // Reset to "all" when student changes
      setSelectedEnrollmentIds([])
      setFilterApplied(false)
      setSelectedAssessmentType('') // Reset assessment type filter
      fetchUuidDetail(studentUuidParam, [])
    } else if (isUuidMode && !studentUuidParam) {
      // No student selected (e.g. just landed on /app/math/student) — clear detail so we don't show stale data
      setUuidDetail(null)
      setHeader(null)
      setAssessments([])
      setInterventions([])
      setScoresHistory([])
      setNotes([])
      setGoals([])
      setSelectedAssessmentType('') // Reset assessment type filter
    }
  }, [isUuidMode, studentUuidParam, fetchUuidDetail])

  // --- Enrollment mode: redirect to UUID mode if we can resolve student_uuid ---
  useEffect(() => {
    if (isEnrollmentMode && enrollmentIdParam && allEnrollments.length > 0) {
      const en = allEnrollments.find((e) => e.enrollment_id === enrollmentIdParam)
      if (en?.student_uuid) {
        navigate(`/app/${subject}/student/${en.student_uuid}`, { replace: true })
      }
    }
  }, [isEnrollmentMode, enrollmentIdParam, allEnrollments, navigate, subject])

  // --- Legacy mode data fetch ---
  useEffect(() => {
    if (!isLegacyMode) return
    if (!selectedId) {
      setStudent(null)
      setAssessments([])
      setInterventions([])
      setScoresHistory([])
      setHeader(null)
      setNotes([])
      setGoals([])
      return
    }
    setLoading(true)
    Promise.all([
      api.getStudent(selectedId),
      isMath ? api.getStudentMathScore(selectedId) : api.getStudentLiteracyScore(selectedId),
      api.getStudentAssessments(selectedId),
      api.getStudentInterventions(selectedId),
    ])
      .then(([s, _sc, a, i]) => {
        setStudent(s)
        setAssessments(a.assessments)
        setInterventions(i.interventions)
        const byPeriod = (
          a.assessments as (Assessment & {
            score_normalized?: number
            overall_literacy_score?: number
            overall_math_score?: number
          })[]
        )
          .filter((x) =>
            isMath ? x.overall_math_score != null : x.score_normalized != null || x.overall_literacy_score != null,
          )
          .map((x) => ({
            period: `${x.assessment_period || ''} ${x.school_year || ''}`.trim(),
            score: Number(
              (isMath ? x.overall_math_score : (x.score_normalized ?? x.overall_literacy_score)) ?? 0,
            ),
            assessment_type: x.assessment_type || undefined,
          }))
        setScoresHistory(byPeriod)
        setHeader(null)
        setNotes([])
        setGoals([])
      })
      .finally(() => setLoading(false))
  }, [isLegacyMode, selectedId, isMath])

  // Is a given enrollment selected? (empty selectedEnrollmentIds = all)
  const isEnrollmentSelected = (eid: string) =>
    selectedEnrollmentIds.length === 0 || selectedEnrollmentIds.includes(eid)

  // --- Handle enrollment filter toggle ---
  const toggleEnrollment = (eid: string) => {
    const allIds = studentEnrollments.map((e) => e.enrollment_id)
    setSelectedEnrollmentIds((prev) => {
      // If currently "all", expand to explicit list minus the toggled one
      const current = prev.length === 0 ? allIds : prev
      const next = current.includes(eid) ? current.filter((id) => id !== eid) : [...current, eid]
      // Don't allow deselecting everything
      if (next.length === 0) return prev
      // If everything is selected, collapse back to empty (= all)
      if (next.length === allIds.length && allIds.every((id) => next.includes(id))) return []
      return next
    })
  }

  // Re-fetch when enrollment selection changes (UUID mode) — skip initial [] (handled by studentUuid effect)
  const [filterApplied, setFilterApplied] = useState(false)
  useEffect(() => {
    if (!filterApplied) return
    if (isUuidMode && studentUuidParam) {
      fetchUuidDetail(studentUuidParam, selectedEnrollmentIds)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEnrollmentIds, filterApplied])

  // Wrap toggle to also mark filter as applied
  const handleToggle = (eid: string) => {
    setFilterApplied(true)
    toggleEnrollment(eid)
  }

  const selectAll = () => {
    setFilterApplied(true)
    setSelectedEnrollmentIds([])
  }
  const deselectToLatestYear = () => {
    if (studentEnrollments.length === 0) return
    const latestYear = studentEnrollments.reduce(
      (max, e) => (e.school_year > max ? e.school_year : max),
      '',
    )
    const latestIds = studentEnrollments
      .filter((e) => e.school_year === latestYear)
      .map((e) => e.enrollment_id)
    setFilterApplied(true)
    setSelectedEnrollmentIds(latestIds)
  }

  // --- Display context: prefer header from API response (uuidDetail); fill blanks from assessments/interventions when present ---
  const displayHeader = (() => {
    if (isLegacyMode && scoresHistory.length > 0) {
      return {
        latest_score: scoresHistory[scoresHistory.length - 1].score,
        tier: null as string | null,
        trend: null as string | null,
        last_assessed_date: null as string | null,
        days_since_assessment: null as number | null,
        has_active_intervention: interventions.some((i) => (i.status ?? '').toLowerCase().includes('active')),
        goal_status: goals.length > 0 ? 'Has goals' : 'No goals',
      }
    }
    const h = (isUuidMode && uuidDetail?.header) ? uuidDetail.header : header
    // Derive KPIs from assessments when we have rows (same fields the table uses)
    const withScores = assessments as (Assessment & { score_normalized?: number; score_value?: string; effective_date?: string; assessment_date?: string })[]
    const hasScore = (a: typeof withScores[0]) => {
      const n = a.score_normalized
      if (n != null && !Number.isNaN(Number(n))) return true
      return false
    }
    const scored = withScores.filter(hasScore)
    const lastWithScore =
      scored.length > 0
        ? [...scored].sort((a, b) => {
            const da = a.effective_date ?? (a as { assessment_date?: string }).assessment_date ?? ''
            const db = b.effective_date ?? (b as { assessment_date?: string }).assessment_date ?? ''
            return db.localeCompare(da)
          })[scored.length - 1]
        : null
    const derivedLatestScore = lastWithScore?.score_normalized != null ? Number(lastWithScore.score_normalized) : null
    const derivedLastDate = lastWithScore
      ? (lastWithScore.effective_date ?? (lastWithScore as { assessment_date?: string }).assessment_date) ?? null
      : null
    const derivedIntervention = interventions.some((i) => (i.status ?? '').toLowerCase().includes('active'))
    const derivedGoalStatus = goals.length > 0 ? 'Has goals' : 'No goals'
    // When we have no header from API, build one from assessments/interventions so KPIs are never blank when data exists
    if (!h) {
      if (assessments.length === 0) return null
      return {
        latest_score: derivedLatestScore,
        tier: null as string | null,
        trend: null as string | null,
        last_assessed_date: derivedLastDate,
        days_since_assessment: null as number | null,
        has_active_intervention: derivedIntervention,
        goal_status: derivedGoalStatus,
      }
    }
    return {
      ...h,
      latest_score: h.latest_score != null && !Number.isNaN(Number(h.latest_score)) ? Number(h.latest_score) : derivedLatestScore,
      last_assessed_date: h.last_assessed_date ?? derivedLastDate,
      has_active_intervention: h.has_active_intervention ?? derivedIntervention,
      goal_status: h.goal_status ?? derivedGoalStatus,
    }
  })()

  const displayName = isUuidMode ? uuidDetail?.display_name : student?.student_name
  const hasData = isUuidMode ? Boolean(uuidDetail) : Boolean(student)

  // Extract unique assessment types from scoresHistory
  const availableAssessmentTypes = (() => {
    const types = new Set<string>()
    scoresHistory.forEach((item) => {
      if (item.assessment_type) {
        types.add(item.assessment_type)
      }
    })
    return Array.from(types).sort()
  })()

  // Initialize selectedAssessmentType to first type when data loads (per student)
  useEffect(() => {
    if (availableAssessmentTypes.length > 0 && !selectedAssessmentType) {
      setSelectedAssessmentType(availableAssessmentTypes[0]!)
    }
  }, [scoresHistory.length]) // Re-initialize when scoresHistory changes (new student/data loaded)

  // Filter scoresHistory based on selected assessment type
  const filteredScoresHistory = scoresHistory.filter((item) => {
    if (!selectedAssessmentType) return true // Show all if nothing selected
    if (!item.assessment_type) return false
    return item.assessment_type === selectedAssessmentType
  })

  const changeSinceLast = (() => {
    if (filteredScoresHistory.length < 2) return null
    const a = filteredScoresHistory[filteredScoresHistory.length - 2].score
    const b = filteredScoresHistory[filteredScoresHistory.length - 1].score
    const delta = b - a
    return { delta, from: a, to: b }
  })()

  const benchmarkMin = 70
  const benchmarkMax = 100

  // Calculate dynamic Y-axis domain based on filtered data
  const yAxisDomain = (() => {
    if (filteredScoresHistory.length === 0) return [0, 105]
    
    const scores = filteredScoresHistory.map((item) => item.score).filter((s) => !isNaN(s) && isFinite(s))
    if (scores.length === 0) return [0, 105]
    
    const minScore = Math.min(...scores)
    const maxScore = Math.max(...scores)
    
    // Ensure benchmark range (70-100) is visible
    const dataMin = Math.min(minScore, benchmarkMin)
    const dataMax = Math.max(maxScore, benchmarkMax)
    
    // Add padding: 10% below min, 10% above max, but cap at reasonable bounds
    const padding = (dataMax - dataMin) * 0.1
    const domainMin = Math.max(0, Math.floor(dataMin - padding))
    const domainMax = Math.min(105, Math.ceil(dataMax + padding))
    
    // Ensure we have at least some range
    if (domainMax - domainMin < 20) {
      return [Math.max(0, domainMin - 10), Math.min(105, domainMax + 10)]
    }
    
    return [domainMin, domainMax]
  })()

  return (
    <div className="mx-auto" style={{ maxWidth: 'var(--content-max-width)' }}>
      <h1 className="text-3xl font-bold mb-4" style={{ fontFamily: 'var(--font-family)', color: '#1F2937' }}>
        {subjectLabel} Student Detail
      </h1>

      {/* --- Student picker --- */}
      {isUuidMode || isEnrollmentMode ? (
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Select student</label>
          <select
            className="border rounded px-3 py-2 w-full max-w-xs"
            value={studentUuidParam ?? ''}
            onChange={(e) => {
              const uuid = e.target.value
              if (uuid) navigate(`/app/${subject}/student/${uuid}`)
            }}
          >
            <option value="">— Select —</option>
            {uniqueStudents.map((s) => (
              <option key={s.studentUuid} value={s.studentUuid}>
                {s.displayName}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Select student</label>
          <select
            className="border rounded px-3 py-2 w-full max-w-xs"
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">— Select —</option>
            {uniqueLegacyStudents.map((s) => (
              <option key={s.student_id} value={s.student_id}>
                {s.student_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* --- Enrollment filter (UUID mode) --- */}
      {isUuidMode && studentEnrollments.length > 0 && (
        <div className="mb-6 p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ color: '#1F2937' }}>Filter by Grade / Year</span>
            <span className="flex gap-2">
              <button
                type="button"
                className="text-xs underline opacity-70 hover:opacity-100"
                onClick={selectAll}
              >
                Select all
              </button>
              <button
                type="button"
                className="text-xs underline opacity-70 hover:opacity-100"
                onClick={deselectToLatestYear}
              >
                Latest year only
              </button>
            </span>
          </div>
          <div className="flex flex-wrap gap-3">
            {studentEnrollments.map((e) => {
              const checked = isEnrollmentSelected(e.enrollment_id)
              return (
                <label
                  key={e.enrollment_id}
                  className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full border cursor-pointer transition-colors"
                  style={
                    checked
                      ? { backgroundColor: '#1E3A5F', color: '#FFFFFF', borderColor: '#1E3A5F' }
                      : { backgroundColor: '#E5E7EB', color: '#1E3A5F', borderColor: '#D1D5DB' }
                  }
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() => handleToggle(e.enrollment_id)}
                  />
                  {e.grade_level} &bull; {e.school_year}
                </label>
              )
            })}
          </div>
        </div>
      )}

      {loading && <p className="text-[var(--color-text)]">Loading...</p>}

      {!loading && hasData && (
        <>
          {/* Top strip KPIs — use displayHeader (from API or legacy fallback) */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4" style={{ marginBottom: '2.5rem' }}>
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', borderLeftWidth: '4px', borderLeftColor: '#1E3A5F', boxShadow: 'none' }}>
              <p className="text-sm opacity-80">Latest Score</p>
              <p className="text-5xl font-semibold" style={{ color: '#1F2937' }}>
                {displayHeader?.latest_score != null
                  ? Number(displayHeader.latest_score).toFixed(1)
                  : filteredScoresHistory.length > 0
                    ? filteredScoresHistory[filteredScoresHistory.length - 1].score.toFixed(1)
                    : scoresHistory.length > 0
                      ? scoresHistory[scoresHistory.length - 1].score.toFixed(1)
                      : '—'}
              </p>
            </div>
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <p className="text-sm opacity-80">Tier / Risk</p>
              <p className="pt-1">
                <RiskBadge tier={displayHeader ? tierToDisplayTier(displayHeader.tier) : undefined} risk={undefined} />
              </p>
            </div>
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <p className="text-sm opacity-80">Trend</p>
              <p className="pt-1">
                <TrendChip trend={displayHeader?.trend ?? undefined} />
              </p>
            </div>
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <p className="text-sm opacity-80">Last assessed</p>
              <p className="text-lg font-medium" style={{ color: '#1F2937' }}>{displayHeader?.last_assessed_date ?? '—'}</p>
              {displayHeader?.days_since_assessment != null && (
                <p className="text-[var(--caption-size)] opacity-70">{displayHeader.days_since_assessment} days since</p>
              )}
            </div>
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <p className="text-sm opacity-80">Intervention</p>
              <p className="text-lg font-medium" style={{ color: '#1F2937' }}>{displayHeader?.has_active_intervention ? 'Active' : 'None'}</p>
            </div>
            <div className="p-4 rounded-lg border" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <p className="text-sm opacity-80">Goal status</p>
              <p className="text-lg font-medium" style={{ color: '#1F2937' }}>{displayHeader?.goal_status ?? '—'}</p>
            </div>
          </div>

          {/* Change since last callout */}
          {changeSinceLast != null && (
            <div
              className="mb-6 p-4 rounded-lg border"
              style={{
                backgroundColor: changeSinceLast.delta >= 0 ? '#F0F7F3' : '#FDF2F2',
                border: '1px solid #E2E8F0',
                borderLeftWidth: '4px',
                borderLeftColor: changeSinceLast.delta >= 0 ? '#1E6B43' : '#9B1C1C',
                boxShadow: 'none',
              }}
            >
              <span className="text-[var(--label-size)] font-medium opacity-80">Change since last: </span>
              <span
                className="font-bold"
                style={{ color: changeSinceLast.delta >= 0 ? '#166534' : '#991B1B' }}
              >
                {changeSinceLast.delta >= 0 ? '+' : ''}
                {changeSinceLast.delta.toFixed(1)} pts
              </span>
              <span className="text-[var(--caption-size)] opacity-70 ml-2">
                ({changeSinceLast.from.toFixed(1)} → {changeSinceLast.to.toFixed(1)})
              </span>
            </div>
          )}

          {/* Score over time with benchmark band */}
          {scoresHistory.length > 0 && (
            <div className="mb-8 rounded-lg border p-4" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-medium" style={{ fontFamily: 'var(--font-family)', color: '#1F2937' }}>Score Over Time</h2>
                  <div className="flex items-center gap-2 text-xs opacity-70">
                    <div className="flex items-center gap-1.5">
                      <div className="w-3 h-3 rounded" style={{ backgroundColor: '#A7D4B8' }}></div>
                      <span>Benchmark range ({benchmarkMin}-{benchmarkMax})</span>
                    </div>
                  </div>
                </div>
                {availableAssessmentTypes.length > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs opacity-70">Assessment type:</span>
                    <select
                      className="border rounded-lg px-2 py-1 text-xs"
                      style={{ backgroundColor: '#F7F9FB', borderColor: '#E2E8F0' }}
                      value={selectedAssessmentType || (availableAssessmentTypes[0] ?? '')}
                      onChange={(e) => setSelectedAssessmentType(e.target.value)}
                    >
                      {availableAssessmentTypes.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={filteredScoresHistory} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="period" tick={{ fontSize: 12, fill: '#475569' }} />
                    <YAxis domain={yAxisDomain} tick={{ fontSize: 12, fill: '#475569' }} />
                    <Tooltip
                      formatter={(value: number, _name: string, props: { payload?: { assessment_type?: string } }) => {
                        const type = props.payload?.assessment_type
                        const formatted = typeof value === 'number' ? Number(value).toFixed(1) : value
                        return type ? [`${formatted} (${type})`, 'Score'] : [formatted, 'Score']
                      }}
                    />
                    <ReferenceArea y1={benchmarkMin} y2={benchmarkMax} fill="#EAF4EF" fillOpacity={0.9} />
                    <Line type="monotone" dataKey="score" stroke="#1E3A5F" strokeWidth={2.5} name="Score" dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Assessments, Interventions, Notes, Goals */}
          <div className="grid md:grid-cols-2 gap-6 mb-6">
            <div className="rounded-lg border overflow-hidden" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <h2 className="text-lg font-medium p-4 border-b" style={{ fontFamily: 'var(--font-family)', borderColor: '#E2E8F0', color: '#1F2937' }}>Assessments</h2>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                      <th className="text-left p-3">Type</th>
                      <th className="text-left p-3">Period</th>
                      <th className="text-left p-3">Score</th>
                      <th className="text-left p-3">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assessments.map((a, idx) => (
                      <tr
                        key={(a as Assessment & { assessment_id?: number }).assessment_id ?? `${a.assessment_type}-${a.assessment_period}-${idx}`}
                        className="border-b"
                        style={{ borderColor: 'var(--color-border)' }}
                      >
                        <td className="p-3">{a.assessment_type}</td>
                        <td className="p-3">{a.assessment_period}</td>
                        <td className="p-3">
                          {(a as Assessment & { score_normalized?: number }).score_value ??
                            ((a as Assessment & { score_normalized?: number }).score_normalized != null
                              ? Number((a as Assessment & { score_normalized?: number }).score_normalized).toFixed(1)
                              : '—')}
                        </td>
                        <td className="p-3">{(a as Assessment & { assessment_date?: string; effective_date?: string }).assessment_date ?? (a as { effective_date?: string }).effective_date ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="rounded-lg border overflow-hidden" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <h2 className="text-lg font-medium p-4 border-b" style={{ fontFamily: 'var(--font-family)', borderColor: '#E2E8F0', color: '#1F2937' }}>Interventions</h2>
              <div className="overflow-x-auto max-h-64 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                      <th className="text-left p-3">Type</th>
                      <th className="text-left p-3">Start</th>
                      <th className="text-left p-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {interventions.map((i, idx) => (
                      <tr
                        key={(i as Intervention & { intervention_id?: number }).intervention_id ?? `${i.start_date}-${idx}`}
                        className="border-b"
                        style={{ borderColor: 'var(--color-border)' }}
                      >
                        <td className="p-3">{i.intervention_type}</td>
                        <td className="p-3">{i.start_date}</td>
                        <td className="p-3">{i.status ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div className="rounded-lg border overflow-hidden" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <h2 className="text-lg font-medium p-4 border-b" style={{ fontFamily: 'var(--font-family)', borderColor: '#E2E8F0', color: '#1F2937' }}>Notes</h2>
              <div className="overflow-x-auto max-h-48 overflow-y-auto p-4">
                {notes.length === 0 ? (
                  <p className="text-[var(--caption-size)] opacity-70">No notes yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {notes.map((n, idx) => (
                      <li key={idx} className="text-sm border-b pb-2" style={{ borderColor: 'var(--color-border)' }}>
                        {(n as { note_text?: string }).note_text ?? JSON.stringify(n)}
                        {(n as { note_date?: string }).note_date && (
                          <span className="block text-[var(--caption-size)] opacity-70 mt-1">
                            {(n as { note_date: string }).note_date}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <div className="rounded-lg border overflow-hidden" style={{ backgroundColor: '#F7F9FB', border: '1px solid #E2E8F0', boxShadow: 'none' }}>
              <h2 className="text-lg font-medium p-4 border-b" style={{ fontFamily: 'var(--font-family)', borderColor: '#E2E8F0', color: '#1F2937' }}>Goals</h2>
              <div className="overflow-x-auto max-h-48 overflow-y-auto p-4">
                {goals.length === 0 ? (
                  <p className="text-[var(--caption-size)] opacity-70">No goals set.</p>
                ) : (
                  <ul className="space-y-2">
                    {goals.map((g, idx) => (
                      <li key={idx} className="text-sm border-b pb-2" style={{ borderColor: 'var(--color-border)' }}>
                        <span className="font-medium">{(g as { measure?: string }).measure ?? 'Goal'}</span>
                        {(g as { baseline_score?: number }).baseline_score != null &&
                          (g as { target_score?: number }).target_score != null && (
                            <span className="ml-2 opacity-80">
                              {Number((g as { baseline_score: number }).baseline_score).toFixed(1)} →{' '}
                              {Number((g as { target_score: number }).target_score).toFixed(1)}
                            </span>
                          )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
