import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import DashboardPage from './pages/DashboardPage'
import GrirDashboard from './pages/GrirDashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/grir" element={<GrirDashboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
