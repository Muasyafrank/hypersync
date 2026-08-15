import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ConfirmProvider } from './context/ConfirmContext';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import ReadingsHistory from './pages/ReadingsHistory';
import LogReading from './pages/LogReading';
import Trend from './pages/Trend';
import ClinicianDashboard from './pages/ClinicianDashboard';
import ClinicianPatientDetail from './pages/ClinicianPatientDetail';
import AdminDashboard from './pages/AdminDashboard';

function PrivateRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    const fallback = user.role === 'admin' ? '/admin' : user.role === 'clinician' ? '/clinician' : '/dashboard';
    return <Navigate to={fallback} replace />;
  }
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/clinician" element={<PrivateRoute allowedRoles={['clinician']}><ClinicianDashboard /></PrivateRoute>} />
      <Route path="/clinician/patients/:patientId" element={<PrivateRoute allowedRoles={['clinician']}><ClinicianPatientDetail /></PrivateRoute>} />
      <Route path="/dashboard" element={<PrivateRoute allowedRoles={['patient']}><Dashboard /></PrivateRoute>} />
      <Route path="/readings" element={<PrivateRoute allowedRoles={['patient']}><ReadingsHistory /></PrivateRoute>} />
      <Route path="/readings/new" element={<PrivateRoute allowedRoles={['patient']}><LogReading /></PrivateRoute>} />
      <Route path="/trend" element={<PrivateRoute allowedRoles={['patient']}><Trend /></PrivateRoute>} />
      <Route path="/admin" element={<PrivateRoute allowedRoles={['admin']}><AdminDashboard /></PrivateRoute>} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </ConfirmProvider>
    </ToastProvider>
  );
}