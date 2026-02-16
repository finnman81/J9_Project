import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type TeacherDashboardResponse } from '../api/client'
import { RiskBadge } from '../components/RiskBadge'

export function TeacherDashboard() {
  const { subject } = useParams<{ subject: string }>()
  const isMath = subject?.toLowerCase() === 'math'
  const [teachers, setTeachers] = useState<string[]>([])
  const [selectedTeacher, setSelectedTeacher] = useState('')
  const [schoolYear, setSchoolYear] = useState('2024-25')
  const [data, setData] = useState<TeacherDashboardResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.getTeachers().then((r) => setTeachers(r.teachers))
  }, [])

  useEffect(() => {
    if (!selectedTeacher) {
      setData(null)
      return
    }
    setLoading(true)
    api.getTeacherDashboard(selectedTeacher, schoolYear, isMath ? 'Math' : 'Reading')
      .then(setData)
      .finally(() => setLoading(false))
  }, [selectedTeacher, schoolYear, isMath])

  const title = 'Teacher Dashboard'
  const scoreCol = isMath ? 'overall_math_score' : 'overall_literacy_score'

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
        {title}
      </h1>

      <div className="flex flex-wrap gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium mb-1">Teacher</label>
          <select
            className="border rounded px-3 py-2 min-w-[200px]"
            value={selectedTeacher}
            onChange={(e) => setSelectedTeacher(e.target.value)}
          >
            <option value="">— Select —</option>
            {teachers.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">School Year</label>
          <select
            className="border rounded px-3 py-2"
            value={schoolYear}
            onChange={(e) => setSchoolYear(e.target.value)}
          >
            <option value="2023-24">2023-24</option>
            <option value="2024-25">2024-25</option>
            <option value="2025-26">2025-26</option>
          </select>
        </div>
      </div>

      {loading && <p>Loading...</p>}
      {!loading && data && (
        <>
          <p className="text-sm opacity-80 mb-4">
            {data.summary.total_students} students | {data.summary.needs_support} need support
          </p>
          <div className="rounded border overflow-hidden" style={{ borderColor: 'var(--color-border)' }}>
            <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[var(--color-surface)]" style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <tr>
                    <th className="text-left p-3">Name</th>
                    <th className="text-left p-3">Grade</th>
                    <th className="text-left p-3">Score</th>
                    <th className="text-left p-3">Tier</th>
                    <th className="text-left p-3">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {data.students.map((s) => (
                    <tr key={s.student_id} className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                      <td className="p-3">{s.student_name}</td>
                      <td className="p-3">{s.grade_level}</td>
                      <td className="p-3">{scoreCol in s && s[scoreCol as keyof typeof s] != null ? Number(s[scoreCol as keyof typeof s]).toFixed(1) : '—'}</td>
                      <td className="p-3"><RiskBadge tier={s.support_tier} /></td>
                      <td className="p-3">{s.trend ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
