import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './themes/ThemeContext'
import { Layout } from './components/Layout'
import { OverviewDashboard } from './pages/OverviewDashboard'
import { StudentDetail } from './pages/StudentDetail'
import { GradeEntry } from './pages/GradeEntry'
import { Analytics } from './pages/Analytics'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/app/reading/overview" replace />} />
          <Route path="/app" element={<Navigate to="/app/reading/overview" replace />} />
          <Route path="/app/:subject" element={<Layout />}>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<OverviewDashboard />} />
            <Route path="student/:studentUuid" element={<StudentDetail />} />
            <Route path="enrollment/:enrollmentId" element={<StudentDetail />} />
            <Route path="student" element={<StudentDetail />} />
            <Route path="grade-entry" element={<GradeEntry />} />
            <Route path="teacher" element={<Navigate to="overview" replace />} />
            <Route path="analytics" element={<Analytics />} />
          </Route>
          <Route path="*" element={<Navigate to="/app/reading/overview" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
