import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { UploadPage, DashboardPage, GrirDashboard, GrirAnalyticsDashboard } from '../features'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/grir" element={<GrirDashboard />} />
        <Route path="/grir-analytics" element={<GrirAnalyticsDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}