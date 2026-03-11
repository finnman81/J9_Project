import { type ReactNode, useEffect, useState, useCallback, useMemo } from 'react'
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

function DetailSectionCard({
  eyebrow = 'Student detail',
  title,
  subtitle,
  actions,
  children,
  className = '',
}: {
  eyebrow?: string
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
            {eyebrow}
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

function DetailMetricCard({
  label,
  value,
  helper,
  accent,
}: {
  label: string
  value: ReactNode
  helper: string
  accent: string
}) {
  return (
    <div
      className="min-w-0 rounded-[24px] border p-5"
      style={{
        borderColor: `${accent}26`,
        background: `linear-gradient(180deg, ${accent}10, #ffffff)`,
      }}
    >
      <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
        {label}
      </p>
      <div className="mt-3 min-w-0" style={{ color: 'var(--color-text-primary)' }}>
        {value}
      </div>
      <p className="mt-3 text-sm leading-5" style={{ color: 'var(--color-text-muted)' }}>
        {helper}
      </p>
    </div>
  )
}

function EmptyStateMessage({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div
      className="rounded-[22px] border px-5 py-8 text-center"
      style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}
    >
      <p className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
        {title}
      </p>
      <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        {description}
      </p>
    </div>
  )
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
      .then(([s, , a, i]) => {
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
          })[0]
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

  const hasData = isUuidMode ? Boolean(uuidDetail) : Boolean(student)

  // Extract unique assessment types from scoresHistory
  const availableAssessmentTypes = useMemo(() => {
    const types = new Set<string>()
    scoresHistory.forEach((item) => {
      if (item.assessment_type) types.add(item.assessment_type)
    })
    return Array.from(types).sort()
  }, [scoresHistory])

  // Initialize selectedAssessmentType to first type when data loads (per student)
  useEffect(() => {
    if (availableAssessmentTypes.length > 0 && !selectedAssessmentType) {
      setSelectedAssessmentType(availableAssessmentTypes[0]!)
    }
  }, [availableAssessmentTypes, selectedAssessmentType])

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

  const studentDisplayName = isUuidMode
    ? uuidDetail?.display_name ?? uniqueStudents.find((s) => s.studentUuid === studentUuidParam)?.displayName ?? 'Select a student'
    : student?.student_name ?? 'Select a student'

  const selectedEnrollmentCount =
    studentEnrollments.length === 0 ? 0 : selectedEnrollmentIds.length === 0 ? studentEnrollments.length : selectedEnrollmentIds.length

  const selectedRecordsLabel = studentEnrollments.length > 0
    ? `${selectedEnrollmentCount} record${selectedEnrollmentCount === 1 ? '' : 's'} in view`
    : 'Single record in view'

  const latestScoreValue = displayHeader?.latest_score != null
    ? Number(displayHeader.latest_score)
    : filteredScoresHistory.length > 0
      ? filteredScoresHistory[filteredScoresHistory.length - 1]!.score
      : scoresHistory.length > 0
        ? scoresHistory[scoresHistory.length - 1]!.score
        : null

  const benchmarkStatus =
    latestScoreValue == null ? 'No benchmark signal' : latestScoreValue >= benchmarkMin ? 'On benchmark' : 'Below benchmark'

  const activeInterventionCount = interventions.filter((i) => (i.status ?? '').toLowerCase().includes('active')).length

  const sortedAssessments = useMemo(
    () =>
      [...assessments].sort((a, b) => {
        const da = (a as Assessment & { assessment_date?: string; effective_date?: string }).assessment_date ??
          (a as { effective_date?: string }).effective_date ??
          ''
        const db = (b as Assessment & { assessment_date?: string; effective_date?: string }).assessment_date ??
          (b as { effective_date?: string }).effective_date ??
          ''
        return db.localeCompare(da)
      }),
    [assessments],
  )

  const sortedInterventions = useMemo(
    () =>
      [...interventions].sort((a, b) => {
        const activeDelta =
          Number((b.status ?? '').toLowerCase().includes('active')) -
          Number((a.status ?? '').toLowerCase().includes('active'))
        if (activeDelta !== 0) return activeDelta
        return (b.start_date ?? '').localeCompare(a.start_date ?? '')
      }),
    [interventions],
  )

  const latestAssessmentLabel =
    filteredScoresHistory[filteredScoresHistory.length - 1]?.assessment_type ??
    scoresHistory[scoresHistory.length - 1]?.assessment_type ??
    'Assessment history'
  const scorePointCount = filteredScoresHistory.length > 0 ? filteredScoresHistory.length : scoresHistory.length
  const latestAssessmentDate =
    displayHeader?.last_assessed_date ??
    ((sortedAssessments[0] as Assessment & { assessment_date?: string; effective_date?: string } | undefined)?.assessment_date ??
      (sortedAssessments[0] as { effective_date?: string } | undefined)?.effective_date ??
      null)

  return (
    <div className="mx-auto" style={{ maxWidth: 'var(--content-max-width)' }}>
      <section className="grid gap-5 2xl:grid-cols-[1.45fr_0.95fr]" style={{ marginBottom: 'var(--section-gap)' }}>
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
            <div className="min-w-0 max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--color-brand-primary)' }}>
                {subjectLabel} student profile
              </p>
              <h1
                className="mt-4 text-[1.9rem] font-semibold leading-tight md:text-[2.35rem]"
                style={{ fontFamily: 'var(--font-family)', color: 'var(--color-text-primary)' }}
              >
                {studentDisplayName}
              </h1>
              <p className="mt-3 text-sm md:text-base" style={{ color: 'var(--color-text-secondary)' }}>
                Review growth, benchmark performance, supports, and assessment history in one student-centered view.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ backgroundColor: 'var(--color-brand-primary-soft)', color: 'var(--color-brand-primary)' }}>
                {subjectLabel} program
              </span>
              <span className="rounded-full px-3 py-1.5 text-xs font-semibold" style={{ backgroundColor: '#F5F7FB', color: 'var(--color-text-secondary)' }}>
                {selectedRecordsLabel}
              </span>
            </div>
          </div>

          <div className="mt-8 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <div
              className="rounded-[28px] border bg-white/88 p-5"
              style={{ borderColor: 'rgba(201, 215, 232, 0.82)' }}
            >
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
                <label className="flex flex-col gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Student
                  {isUuidMode || isEnrollmentMode ? (
                    <select
                      className="h-11 rounded-[16px] border px-4"
                      style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
                      value={studentUuidParam ?? ''}
                      onChange={(e) => {
                        const uuid = e.target.value
                        if (uuid) navigate(`/app/${subject}/student/${uuid}`)
                      }}
                    >
                      <option value="">Select a student</option>
                      {uniqueStudents.map((s) => (
                        <option key={s.studentUuid} value={s.studentUuid}>
                          {s.displayName}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <select
                      className="h-11 rounded-[16px] border px-4"
                      style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF' }}
                      value={selectedId ?? ''}
                      onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">Select a student</option>
                      {uniqueLegacyStudents.map((s) => (
                        <option key={s.student_id} value={s.student_id}>
                          {s.student_name}
                        </option>
                      ))}
                    </select>
                  )}
                </label>
                <div className="flex items-end">
                  <div className="rounded-[16px] border px-4 py-3 text-sm" style={{ borderColor: 'rgba(201, 215, 232, 0.82)', backgroundColor: '#FBFDFF', color: 'var(--color-text-secondary)' }}>
                    {studentEnrollments.length > 0 ? `${selectedEnrollmentCount} records selected` : latestAssessmentLabel}
                  </div>
                </div>
              </div>

              {isUuidMode && studentEnrollments.length > 0 && (
                <>
                  <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      Records included
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={selectAll}
                        className="rounded-full border px-3 py-1.5 text-xs font-semibold"
                        style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: '#FBFDFF' }}
                      >
                        All records
                      </button>
                      <button
                        type="button"
                        onClick={deselectToLatestYear}
                        className="rounded-full border px-3 py-1.5 text-xs font-semibold"
                        style={{ borderColor: 'var(--color-border-subtle)', color: 'var(--color-text-secondary)', backgroundColor: '#FBFDFF' }}
                      >
                        Latest year
                      </button>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {studentEnrollments.map((e) => {
                      const checked = isEnrollmentSelected(e.enrollment_id)

                      return (
                        <label
                          key={e.enrollment_id}
                          className="inline-flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold"
                          style={
                            checked
                              ? { backgroundColor: 'var(--color-brand-primary-soft)', color: 'var(--color-brand-primary)', borderColor: 'rgba(151, 180, 233, 0.65)' }
                              : { backgroundColor: '#F7FAFF', color: 'var(--color-text-secondary)', borderColor: 'rgba(201, 215, 232, 0.82)' }
                          }
                        >
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={checked}
                            onChange={() => handleToggle(e.enrollment_id)}
                          />
                          {e.grade_level} · {e.school_year}
                        </label>
                      )
                    })}
                  </div>
                </>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <DetailMetricCard
                label="Latest score"
                value={
                  <p className="text-[clamp(1.7rem,2.6vw,2.3rem)] font-semibold leading-tight tracking-[-0.02em]">
                    {latestScoreValue != null ? latestScoreValue.toFixed(1) : 'N/A'}
                  </p>
                }
                helper={latestAssessmentLabel}
                accent="#295BA7"
              />
              <DetailMetricCard
                label="Tier / risk"
                value={<RiskBadge tier={displayHeader ? tierToDisplayTier(displayHeader.tier) : undefined} risk={undefined} />}
                helper={benchmarkStatus}
                accent="#17663D"
              />
              <DetailMetricCard
                label="Trend"
                value={<TrendChip trend={displayHeader?.trend ?? undefined} />}
                helper={changeSinceLast ? `${changeSinceLast.delta >= 0 ? '+' : ''}${changeSinceLast.delta.toFixed(1)} points since last measure` : 'Need at least two assessments for growth'}
                accent="#B23754"
              />
              <DetailMetricCard
                label="Supports"
                value={<p className="text-[1.35rem] font-semibold leading-tight">{activeInterventionCount > 0 ? `${activeInterventionCount} active` : 'None active'}</p>}
                helper={displayHeader?.goal_status ?? (goals.length > 0 ? 'Goals on file' : 'No goals on file')}
                accent="#F3B455"
              />
            </div>
          </div>
        </div>

        <DetailSectionCard
          eyebrow="Snapshot"
          title="Support snapshot"
          subtitle="Most recent academic and support context."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Last assessed
              </p>
              <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {latestAssessmentDate ?? 'No assessment date'}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {displayHeader?.days_since_assessment != null ? `${displayHeader.days_since_assessment} days since latest assessment` : 'Date not available'}
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Goal status
              </p>
              <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {displayHeader?.goal_status ?? (goals.length > 0 ? 'Goals on file' : 'No goals')}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {goals.length > 0 ? `${goals.length} goal${goals.length === 1 ? '' : 's'} recorded` : 'No active goal records'}
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Assessments recorded
              </p>
              <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {sortedAssessments.length}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {scorePointCount} chart point{scorePointCount === 1 ? '' : 's'} in the current view
              </p>
            </div>
            <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                Change since last
              </p>
              <p className="mt-2 text-lg font-semibold" style={{ color: changeSinceLast && changeSinceLast.delta < 0 ? '#B23754' : '#17663D' }}>
                {changeSinceLast ? `${changeSinceLast.delta >= 0 ? '+' : ''}${changeSinceLast.delta.toFixed(1)} pts` : 'N/A'}
              </p>
              <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {changeSinceLast ? `${changeSinceLast.from.toFixed(1)} to ${changeSinceLast.to.toFixed(1)}` : 'Not enough assessments to compare'}
              </p>
            </div>
          </div>
        </DetailSectionCard>
      </section>

      {loading && (
        <div className="py-14 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Loading student profile...
        </div>
      )}

      {!loading && !hasData && (
        <DetailSectionCard
          eyebrow="Student detail"
          title="Select a student"
          subtitle="Choose a student to review progress, supports, and assessment history."
          className="mb-[var(--section-gap)]"
        >
          <EmptyStateMessage
            title="No student selected yet"
            description="Use the student picker to open an individual profile. Once selected, charts, assessments, supports, notes, and goals appear here."
          />
        </DetailSectionCard>
      )}

      {!loading && hasData && (
        <>
          <DetailSectionCard
            eyebrow="Progress"
            title="Progress over time"
            subtitle="Assessment history across the selected records."
            actions={
              availableAssessmentTypes.length > 0 ? (
                <label className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Assessment
                  <select
                    className="h-10 rounded-[14px] border px-3"
                    style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: '#FBFDFF', color: 'var(--color-text-primary)' }}
                    value={selectedAssessmentType || (availableAssessmentTypes[0] ?? '')}
                    onChange={(e) => setSelectedAssessmentType(e.target.value)}
                  >
                    {availableAssessmentTypes.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>
              ) : undefined
            }
            className="mb-[var(--section-gap)]"
          >
            <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Benchmark band
                </p>
                <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {benchmarkMin}–{benchmarkMax}
                </p>
                <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Target range for the selected assessment view
                </p>
              </div>
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Current assessment
                </p>
                <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {latestAssessmentLabel}
                </p>
                <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  {scorePointCount} plotted point{scorePointCount === 1 ? '' : 's'}
                </p>
              </div>
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Intervention status
                </p>
                <p className="mt-2 text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {activeInterventionCount > 0 ? `${activeInterventionCount} active` : 'No active supports'}
                </p>
                <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  Review supports alongside the chart trend.
                </p>
              </div>
              <div className="rounded-[22px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                  Momentum
                </p>
                <p className="mt-2 text-lg font-semibold" style={{ color: changeSinceLast && changeSinceLast.delta < 0 ? '#B23754' : '#17663D' }}>
                  {changeSinceLast ? `${changeSinceLast.delta >= 0 ? '+' : ''}${changeSinceLast.delta.toFixed(1)} pts` : 'No comparison'}
                </p>
                <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  {changeSinceLast ? `${changeSinceLast.from.toFixed(1)} → ${changeSinceLast.to.toFixed(1)}` : 'Add another assessment for change over time'}
                </p>
              </div>
            </div>

            {scoresHistory.length > 0 ? (
              <div className="h-[320px] rounded-[24px] border p-4" style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={filteredScoresHistory} margin={{ top: 10, right: 16, left: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 12, fill: '#62748D' }} axisLine={false} tickLine={false} />
                    <YAxis domain={yAxisDomain} tick={{ fontSize: 12, fill: '#62748D' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: 16, borderColor: '#D9E2EC', boxShadow: '0 16px 32px rgba(20, 33, 61, 0.12)' }}
                      formatter={(value: number | string | undefined, _name?: string, props?: { payload?: { assessment_type?: string } }) => {
                        const type = props?.payload?.assessment_type
                        const formatted = typeof value === 'number' ? Number(value).toFixed(1) : value ?? 'N/A'
                        return type ? [`${formatted} (${type})`, 'Score'] : [formatted, 'Score']
                      }}
                    />
                    <ReferenceArea y1={benchmarkMin} y2={benchmarkMax} fill="#EAF4EF" fillOpacity={0.95} />
                    <Line type="monotone" dataKey="score" stroke="#295BA7" strokeWidth={3} name="Score" dot={{ r: 4, strokeWidth: 2, fill: '#FFFFFF' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyStateMessage
                title="No assessment chart yet"
                description="Once assessments are available for this student, the progress trend appears here."
              />
            )}
          </DetailSectionCard>

          <section className="grid gap-5 xl:grid-cols-2" style={{ marginBottom: 'var(--section-gap)' }}>
            <DetailSectionCard
              eyebrow="Records"
              title="Assessments"
              subtitle={`${sortedAssessments.length} assessment${sortedAssessments.length === 1 ? '' : 's'} recorded`}
            >
              {sortedAssessments.length > 0 ? (
                <div className="overflow-x-auto rounded-[22px] border" style={{ borderColor: 'rgba(217, 226, 236, 0.9)' }}>
                  <table className="w-full text-sm">
                    <thead style={{ backgroundColor: 'var(--table-header-bg)' }}>
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Type</th>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Period</th>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Score</th>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedAssessments.map((a, idx) => (
                        <tr
                          key={(a as Assessment & { assessment_id?: number }).assessment_id ?? `${a.assessment_type}-${a.assessment_period}-${idx}`}
                          style={{ borderTop: '1px solid rgba(217, 226, 236, 0.9)' }}
                        >
                          <td className="px-4 py-3">{a.assessment_type}</td>
                          <td className="px-4 py-3">{a.assessment_period}</td>
                          <td className="px-4 py-3">
                            {(a as Assessment & { score_normalized?: number }).score_value ??
                              ((a as Assessment & { score_normalized?: number }).score_normalized != null
                                ? Number((a as Assessment & { score_normalized?: number }).score_normalized).toFixed(1)
                                : 'N/A')}
                          </td>
                          <td className="px-4 py-3">
                            {(a as Assessment & { assessment_date?: string; effective_date?: string }).assessment_date ??
                              (a as { effective_date?: string }).effective_date ??
                              'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyStateMessage
                  title="No assessments recorded"
                  description="Add an assessment to start building the student’s performance history."
                />
              )}
            </DetailSectionCard>

            <DetailSectionCard
              eyebrow="Supports"
              title="Interventions"
              subtitle={`${sortedInterventions.length} intervention${sortedInterventions.length === 1 ? '' : 's'} recorded`}
            >
              {sortedInterventions.length > 0 ? (
                <div className="overflow-x-auto rounded-[22px] border" style={{ borderColor: 'rgba(217, 226, 236, 0.9)' }}>
                  <table className="w-full text-sm">
                    <thead style={{ backgroundColor: 'var(--table-header-bg)' }}>
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Type</th>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Start</th>
                        <th className="px-4 py-3 text-left font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedInterventions.map((i, idx) => (
                        <tr
                          key={(i as Intervention & { intervention_id?: number }).intervention_id ?? `${i.start_date}-${idx}`}
                          style={{ borderTop: '1px solid rgba(217, 226, 236, 0.9)' }}
                        >
                          <td className="px-4 py-3">{i.intervention_type}</td>
                          <td className="px-4 py-3">{i.start_date}</td>
                          <td className="px-4 py-3">{i.status ?? 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyStateMessage
                  title="No interventions recorded"
                  description="Intervention plans and support services appear here when they are added for this student."
                />
              )}
            </DetailSectionCard>
          </section>

          <section className="grid gap-5 xl:grid-cols-2">
            <DetailSectionCard
              eyebrow="Collaboration"
              title="Notes"
              subtitle={notes.length > 0 ? `${notes.length} note${notes.length === 1 ? '' : 's'} recorded` : 'No notes on file'}
            >
              {notes.length > 0 ? (
                <div className="space-y-3">
                  {notes.map((n, idx) => (
                    <div
                      key={idx}
                      className="rounded-[20px] border px-4 py-3"
                      style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}
                    >
                      <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                        {(n as { note_text?: string }).note_text ?? JSON.stringify(n)}
                      </p>
                      {(n as { note_date?: string }).note_date && (
                        <p className="mt-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {(n as { note_date: string }).note_date}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyStateMessage
                  title="No notes yet"
                  description="Teacher or intervention notes can live here for a fuller student narrative."
                />
              )}
            </DetailSectionCard>

            <DetailSectionCard
              eyebrow="Goals"
              title="Student goals"
              subtitle={goals.length > 0 ? `${goals.length} goal${goals.length === 1 ? '' : 's'} on file` : 'No goals on file'}
            >
              {goals.length > 0 ? (
                <div className="space-y-3">
                  {goals.map((g, idx) => (
                    <div
                      key={idx}
                      className="rounded-[20px] border px-4 py-3"
                      style={{ borderColor: 'rgba(217, 226, 236, 0.9)', backgroundColor: '#FBFDFF' }}
                    >
                      <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                        {(g as { measure?: string }).measure ?? 'Goal'}
                      </p>
                      {(g as { baseline_score?: number }).baseline_score != null &&
                        (g as { target_score?: number }).target_score != null && (
                          <p className="mt-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                            {Number((g as { baseline_score: number }).baseline_score).toFixed(1)} →{' '}
                            {Number((g as { target_score: number }).target_score).toFixed(1)}
                          </p>
                        )}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyStateMessage
                  title="No goals set"
                  description="Progress goals and target measures can be tracked here once they are created."
                />
              )}
            </DetailSectionCard>
          </section>
        </>
      )}
    </div>
  )
}
