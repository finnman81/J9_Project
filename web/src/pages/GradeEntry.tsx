import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type Student, type AddAssessmentBody } from '../api/client'

const PERIODS = ['Fall', 'Winter', 'Spring', 'EOY']
const SCHOOL_YEARS = ['2024-25', '2023-24', '2025-26']

const READING_TYPES = [
  'Reading_Level', 'Sight_Words', 'Spelling', 'Spelling_Inventory', 'Benchmark',
  'Easy_CBM', 'Phonics_Survey', 'ORF', 'NWF-CLS', 'NWF-WWR', 'PSF', 'FSF', 'Maze', 'Retell',
  'ERB_Reading_Comp', 'ERB_Vocabulary', 'ERB_Writing_Mechanics', 'ERB_Writing_Concepts',
]
const MATH_TYPES = [
  'NIF', 'NNF', 'AQD', 'MNF', 'Math_Computation', 'Math_Concepts_Application', 'Math_Composite',
  'ERB_Mathematics', 'ERB_Verbal_Reasoning', 'ERB_Quant_Reasoning',
]

export function GradeEntry() {
  const { subject } = useParams<{ subject: string }>()
  const isMath = subject?.toLowerCase() === 'math'
  const [students, setStudents] = useState<Student[]>([])
  const [studentId, setStudentId] = useState<number | null>(null)
  const [assessmentType, setAssessmentType] = useState('')
  const [period, setPeriod] = useState('Fall')
  const [schoolYear, setSchoolYear] = useState('2024-25')
  const [scoreValue, setScoreValue] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    api.getStudents().then((r) => setStudents(r.students))
  }, [])

  // Deduplicate: keep only the most-recent school_year entry per student_name
  const uniqueStudents = (() => {
    const map = new Map<string, Student>()
    for (const s of students) {
      const existing = map.get(s.student_name)
      if (!existing || s.school_year > existing.school_year) {
        map.set(s.student_name, s)
      }
    }
    return Array.from(map.values())
  })()

  const types = isMath ? MATH_TYPES : READING_TYPES

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!studentId || !assessmentType) {
      setMessage({ type: 'error', text: 'Select student and assessment type.' })
      return
    }
    setSaving(true)
    setMessage(null)
    const body: AddAssessmentBody = {
      student_id: studentId,
      assessment_type: assessmentType,
      assessment_period: period,
      school_year: schoolYear,
      score_value: scoreValue || undefined,
      notes: notes || undefined,
      subject_area: isMath ? 'Math' : 'Reading',
    }
    api.postAssessment(body)
      .then(() => {
        setMessage({ type: 'success', text: 'Assessment saved. Scores recalculated.' })
        setScoreValue('')
        setNotes('')
      })
      .catch((err) => setMessage({ type: 'error', text: err.message }))
      .finally(() => setSaving(false))
  }

  const title = isMath ? 'Math Grade Entry' : 'Grade Entry'

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4" style={{ fontFamily: 'var(--font-family)' }}>
        {title}
      </h1>
      <p className="text-sm opacity-80 mb-6">Single student entry. For bulk entry, use the Streamlit app during migration.</p>

      <form onSubmit={handleSubmit} className="max-w-xl space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Student *</label>
          <select
            className="w-full border rounded px-3 py-2"
            value={studentId ?? ''}
            onChange={(e) => setStudentId(e.target.value ? Number(e.target.value) : null)}
            required
          >
            <option value="">— Select —</option>
            {uniqueStudents.map((s) => (
              <option key={s.student_id} value={s.student_id}>
                {s.student_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Assessment Type *</label>
          <select
            className="w-full border rounded px-3 py-2"
            value={assessmentType}
            onChange={(e) => setAssessmentType(e.target.value)}
            required
          >
            <option value="">— Select —</option>
            {types.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Period *</label>
            <select className="w-full border rounded px-3 py-2" value={period} onChange={(e) => setPeriod(e.target.value)}>
              {PERIODS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">School Year *</label>
            <select className="w-full border rounded px-3 py-2" value={schoolYear} onChange={(e) => setSchoolYear(e.target.value)}>
              {SCHOOL_YEARS.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Score Value</label>
          <input
            type="text"
            className="w-full border rounded px-3 py-2"
            value={scoreValue}
            onChange={(e) => setScoreValue(e.target.value)}
            placeholder="e.g. 85 or C/D"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Notes</label>
          <input
            type="text"
            className="w-full border rounded px-3 py-2"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        {message && (
          <p className={message.type === 'success' ? 'text-green-700' : 'text-red-600'}>
            {message.text}
          </p>
        )}
        <button
          type="submit"
          className="px-4 py-2 rounded font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--color-primary)' }}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Assessment'}
        </button>
      </form>
    </div>
  )
}
