const API_BASE = import.meta.env.VITE_API_URL || ''

/** Optional options for API requests (e.g. AbortSignal for cancellation). */
export type ApiRequestOptions = { signal?: AbortSignal }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    let message = text
    try {
      const j = JSON.parse(text)
      if (typeof j?.detail === 'string') message = j.detail
      else if (j?.detail && typeof j.detail === 'object' && typeof (j.detail as { message?: string }).message === 'string')
        message = (j.detail as { message: string }).message
      else if (Array.isArray(j?.detail)) message = j.detail.map((d: { msg?: string }) => d?.msg ?? d).join('; ')
    } catch {
      // keep message as text
    }
    throw new Error(message)
  }
  return res.json()
}

function buildMetricsParams(params?: MetricsParams): string {
  if (!params) return ''
  const q = new URLSearchParams()
  if (params.teacher_name) q.set('teacher_name', params.teacher_name)
  if (params.school_year) q.set('school_year', params.school_year)
  if (params.subject) q.set('subject', params.subject)
  if (params.grade_level) q.set('grade_level', params.grade_level)
  if (params.class_name) q.set('class_name', params.class_name)
  if (params.current_period) q.set('current_period', params.current_period)
  if (params.current_school_year) q.set('current_school_year', params.current_school_year)
  const s = q.toString()
  return s ? `?${s}` : ''
}

export type MetricsParams = {
  teacher_name?: string
  school_year?: string
  subject?: string
  grade_level?: string
  class_name?: string
  current_period?: string
  current_school_year?: string
}

export interface TeacherKpisResponse {
  total_students: number
  assessed_students: number
  assessed_pct: number
  monitor_count: number
  monitor_pct: number
  needs_support_count: number
  needs_support_pct: number
  support_gap_count: number
  support_gap_pct: number
  overdue_count: number
  overdue_pct: number
  median_days_since_assessment: number | null
  intervention_coverage_count: number
  intervention_coverage_pct: number
  assessed_this_window_count: number
  assessed_this_window_pct: number
  tier_moved_up_count: number
  tier_moved_down_count: number
}

export interface PriorityStudentRow {
  enrollment_id: string
  student_uuid?: string
  display_name: string
  teacher_name?: string | null
  school_year: string
  grade_level: string
  class_name?: string | null
  subject_area: string
  latest_score?: number | null
  support_status?: string | null
  tier: string
  trend?: string | null
  days_since_assessment?: number | null
  has_active_intervention: boolean
  priority_score: number
  reasons?: string | null
  reason_chips?: string[]
}

export interface PriorityStudentsResponse {
  rows: PriorityStudentRow[]
  flagged_intensive: number
  flagged_strategic: number
  total_flagged: number
}

export interface GrowthMetricsResponse {
  median_growth: number | null
  avg_growth: number | null
  pct_improving: number
  pct_declining: number
  pct_stable: number
  students_with_growth_data: number
  max_growth: number | null
  min_growth: number | null
}

export interface DistributionResponse {
  bins: { bin_min: number; bin_max: number; count: number; pct?: number }[]
  avg_by_grade: { grade_level: string; average_score: number; pct_needs_support?: number }[]
  support_threshold: number | null
  benchmark_threshold: number | null
}

export interface SupportTrendRow {
  school_year: string
  pct_needs_support: number
  needs_support: number
  total: number
}

export interface SupportTrendResponse {
  rows: SupportTrendRow[]
}

export interface AssessmentAverageRow {
  subject_area: string
  assessment_type: string
  average_score: number
  count: number
}

export interface AssessmentAveragesResponse {
  rows: AssessmentAverageRow[]
}

export interface ErbComparisonRow {
  grade_level: string
  subtest: string
  subtest_label: string
  our_avg_stanine: number
  ind_avg_stanine: number
  diff_stanine: number
  our_avg_percentile: number
  ind_avg_percentile: number
  diff_percentile: number
}

export interface ErbComparisonResponse {
  rows: ErbComparisonRow[]
}

export interface EnrollmentDetailResponse {
  enrollment: Enrollment
  header: {
    latest_score: number | null
    tier: string | null
    trend: string | null
    last_assessed_date: string | null
    days_since_assessment: number | null
    has_active_intervention: boolean
    goal_status: string
  }
  score_over_time: { period: string; score: number; assessment_type?: string }[]
  assessments: Assessment[]
  interventions: Intervention[]
  notes: Record<string, unknown>[]
  goals: Record<string, unknown>[]
}

/** Student detail aggregated across multiple enrollments. */
export interface StudentDetailByUuidResponse {
  student_uuid: string
  display_name: string
  enrollments: Enrollment[]
  selected_enrollment_ids: string[]
  header: {
    latest_score: number | null
    tier: string | null
    trend: string | null
    last_assessed_date: string | null
    days_since_assessment: number | null
    has_active_intervention: boolean
    goal_status: string
  }
  score_over_time: { period: string; score: number; assessment_type?: string }[]
  assessments: Assessment[]
  interventions: Intervention[]
  notes: Record<string, unknown>[]
  goals: Record<string, unknown>[]
}

export const api = {
  getStudents: (params?: { grade_level?: string; class_name?: string; teacher_name?: string; school_year?: string }) => {
    const q = new URLSearchParams()
    if (params?.grade_level) q.set('grade_level', params.grade_level)
    if (params?.class_name) q.set('class_name', params.class_name)
    if (params?.teacher_name) q.set('teacher_name', params.teacher_name)
    if (params?.school_year) q.set('school_year', params.school_year)
    const query = q.toString()
    return request<{ students: Student[] }>(`/api/students${query ? `?${query}` : ''}`)
  },
  getStudent: (id: number) => request<Student>(`/api/students/${id}`),
  createStudent: (body: { student_name: string; grade_level: string; class_name?: string; teacher_name?: string; school_year?: string }) =>
    request<{ student_id: number }>('/api/students', { method: 'POST', body: JSON.stringify(body) }),
  getStudentAssessments: (id: number, school_year?: string) =>
    request<{ assessments: Assessment[] }>(`/api/students/${id}/assessments${school_year ? `?school_year=${encodeURIComponent(school_year)}` : ''}`),
  getStudentInterventions: (id: number) => request<{ interventions: Intervention[] }>(`/api/students/${id}/interventions`),
  getStudentLiteracyScore: (id: number, school_year?: string) =>
    request<{ score: LiteracyScore | null }>(`/api/students/${id}/literacy-score${school_year ? `?school_year=${encodeURIComponent(school_year)}` : ''}`),
  getStudentMathScore: (id: number, school_year?: string) =>
    request<{ score: MathScore | null }>(`/api/students/${id}/math-score${school_year ? `?school_year=${encodeURIComponent(school_year)}` : ''}`),

  getEnrollments: (params?: { grade_level?: string; class_name?: string; teacher_name?: string; school_year?: string }) => {
    const q = new URLSearchParams()
    if (params?.grade_level) q.set('grade_level', params.grade_level)
    if (params?.class_name) q.set('class_name', params.class_name)
    if (params?.teacher_name) q.set('teacher_name', params.teacher_name)
    if (params?.school_year) q.set('school_year', params.school_year)
    const query = q.toString()
    return request<{ enrollments: Enrollment[] }>(`/api/enrollments${query ? `?${query}` : ''}`)
  },
  getEnrollment: (enrollmentId: string) => request<Enrollment>(`/api/enrollments/${enrollmentId}`),
  getEnrollmentAssessments: (enrollmentId: string, school_year?: string) =>
    request<{ assessments: Assessment[] }>(`/api/enrollments/${enrollmentId}/assessments${school_year ? `?school_year=${encodeURIComponent(school_year)}` : ''}`),
  getEnrollmentInterventions: (enrollmentId: string) =>
    request<{ interventions: Intervention[] }>(`/api/enrollments/${enrollmentId}/interventions`),
  getEnrollmentLiteracyScore: (enrollmentId: string, school_year?: string) =>
    request<{ score: LiteracyScore | null }>(`/api/enrollments/${enrollmentId}/literacy-score${school_year ? `?school_year=${encodeURIComponent(school_year)}` : ''}`),
  getEnrollmentMathScore: (enrollmentId: string, school_year?: string) =>
    request<{ score: MathScore | null }>(`/api/enrollments/${enrollmentId}/math-score${school_year ? `?school_year=${encodeURIComponent(school_year)}` : ''}`),
  getEnrollmentDetail: (enrollmentId: string, subject?: string, school_year?: string) => {
    const q = new URLSearchParams()
    if (subject) q.set('subject', subject)
    if (school_year) q.set('school_year', school_year)
    const query = q.toString()
    return request<EnrollmentDetailResponse>(`/api/enrollments/${enrollmentId}/detail${query ? `?${query}` : ''}`)
  },
  /** Student detail aggregated across enrollments (by student_uuid). */
  getStudentDetailByUuid: (studentUuid: string, subject?: string, enrollmentIds?: string[]) => {
    const q = new URLSearchParams()
    if (subject) q.set('subject', subject)
    if (enrollmentIds && enrollmentIds.length > 0) q.set('enrollment_ids', enrollmentIds.join(','))
    const query = q.toString()
    return request<StudentDetailByUuidResponse>(`/api/student-detail/${studentUuid}${query ? `?${query}` : ''}`)
  },
  getTeacherKpis: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<TeacherKpisResponse>(`/api/metrics/teacher-kpis${q}`, { signal: options?.signal })
  },
  getPriorityStudents: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<PriorityStudentsResponse>(`/api/metrics/priority-students${q}`, { signal: options?.signal })
  },
  getGrowthMetrics: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<GrowthMetricsResponse>(`/api/metrics/growth${q}`, { signal: options?.signal })
  },
  getDistribution: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<DistributionResponse>(`/api/metrics/distribution${q}`, { signal: options?.signal })
  },
  getSupportTrend: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<SupportTrendResponse>(`/api/metrics/support-trend${q}`, { signal: options?.signal })
  },
  getAssessmentAverages: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<AssessmentAveragesResponse>(`/api/metrics/assessment-averages${q}`, { signal: options?.signal })
  },
  getErbComparison: (params?: MetricsParams, options?: ApiRequestOptions) => {
    const q = buildMetricsParams(params)
    return request<ErbComparisonResponse>(`/api/metrics/erb-comparison${q}`, { signal: options?.signal })
  },
  getDashboardReading: (params?: { grade_level?: string; class_name?: string; teacher_name?: string; school_year?: string }) => {
    const q = new URLSearchParams()
    if (params?.grade_level) q.set('grade_level', params.grade_level)
    if (params?.class_name) q.set('class_name', params.class_name)
    if (params?.teacher_name) q.set('teacher_name', params.teacher_name)
    if (params?.school_year) q.set('school_year', params.school_year)
    const query = q.toString()
    return request<DashboardResponse>(`/api/dashboard/reading${query ? `?${query}` : ''}`)
  },
  getDashboardMath: (params?: { grade_level?: string; class_name?: string; teacher_name?: string; school_year?: string }) => {
    const q = new URLSearchParams()
    if (params?.grade_level) q.set('grade_level', params.grade_level)
    if (params?.class_name) q.set('class_name', params.class_name)
    if (params?.teacher_name) q.set('teacher_name', params.teacher_name)
    if (params?.school_year) q.set('school_year', params.school_year)
    const query = q.toString()
    return request<DashboardResponse>(`/api/dashboard/math${query ? `?${query}` : ''}`)
  },
  getDashboardFilters: (options?: ApiRequestOptions) =>
    request<{ grade_levels: string[]; classes: string[]; teachers: string[]; school_years: string[] }>('/api/dashboard/filters', { signal: options?.signal }),
  getTeachers: (options?: ApiRequestOptions) =>
    request<{ teachers: string[] }>('/api/teacher/teachers', { signal: options?.signal }),
  getTeacherDashboard: (teacher: string, school_year: string, subject: 'Reading' | 'Math' = 'Reading', options?: ApiRequestOptions) =>
    request<TeacherDashboardResponse>(`/api/teacher/dashboard?teacher=${encodeURIComponent(teacher)}&school_year=${encodeURIComponent(school_year)}&subject=${subject}`, { signal: options?.signal }),
  postAssessment: (body: AddAssessmentBody) => request<{ ok: boolean }>('/api/assessments', { method: 'POST', body: JSON.stringify(body) }),
  postIntervention: (body: AddInterventionBody) => request<{ ok: boolean }>('/api/interventions', { method: 'POST', body: JSON.stringify(body) }),
}

export interface Student {
  student_id: number
  student_name: string
  grade_level: string
  class_name?: string | null
  teacher_name?: string | null
  school_year: string
}

/** Enrollment = one student in one grade/year/class context (student_enrollments + students_core). */
export interface Enrollment {
  enrollment_id: string
  display_name: string
  grade_level: string
  class_name?: string | null
  teacher_name?: string | null
  school_year: string
  student_uuid?: string
  legacy_student_id?: number | null
}

export interface Assessment {
  assessment_id?: number
  student_id: number
  assessment_type: string
  assessment_period: string
  school_year: string
  score_value?: string | null
  score_normalized?: number | null
  assessment_date?: string | null
  notes?: string | null
  subject_area?: string
}

export interface Intervention {
  intervention_id?: number
  student_id: number
  intervention_type: string
  start_date: string
  end_date?: string | null
  status?: string
  notes?: string | null
  subject_area?: string | null
}

export interface LiteracyScore {
  overall_literacy_score?: number | null
  risk_level?: string | null
  trend?: string | null
  assessment_period?: string | null
}

export interface MathScore {
  overall_math_score?: number | null
  risk_level?: string | null
  trend?: string | null
  assessment_period?: string | null
}

export interface DashboardSummary {
  total_students: number
  needs_support: number
  avg_score: number | null
  completion_rate: number
  health: Record<string, unknown>
  intervention_coverage: string
}

/** Dashboard row: enrollment-based (enrollment_id, display_name) or legacy (student_id, student_name). */
export type DashboardStudentRow = (Enrollment | Student) & {
  overall_literacy_score?: number | null
  overall_math_score?: number | null
  risk_level?: string | null
  trend?: string | null
  support_tier?: string | null
  assessment_period?: string | null
}

export interface DashboardResponse {
  summary: DashboardSummary
  students: DashboardStudentRow[]
  priority_students: Record<string, unknown>[]
  growth_summary: { median_growth: number | null; pct_improving: number; pct_declining: number; n: number }
  score_distribution: number[]
  by_grade: { grade_level: string; average_score: number }[]
}

export interface TeacherDashboardResponse {
  teacher: string
  school_year: string
  subject: string
  students: (Student & { support_tier?: string | null; overall_literacy_score?: number | null; overall_math_score?: number | null; risk_level?: string | null; trend?: string | null })[]
  summary: { total_students: number; needs_support: number }
  priority_students: Record<string, unknown>[]
  growth_summary: Record<string, unknown>
}

export interface AddAssessmentBody {
  student_id: number
  assessment_type: string
  assessment_period: string
  school_year: string
  score_value?: string | null
  score_normalized?: number | null
  assessment_date?: string | null
  notes?: string | null
  concerns?: string | null
  subject_area?: string
  raw_score?: number | null
  scaled_score?: number | null
}

export interface AddInterventionBody {
  student_id: number
  intervention_type: string
  start_date: string
  end_date?: string | null
  frequency?: string | null
  duration_minutes?: number | null
  status?: string
  notes?: string | null
  subject_area?: string | null
}
