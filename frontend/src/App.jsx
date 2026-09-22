import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ConfirmProvider } from './context/ConfirmContext';
import ErrorBoundary from './components/ErrorBoundary';
import Loader from './components/ui/Loader';
import { roleHome } from './utils/format';

// Route-level code splitting: a patient never downloads the admin or
// clinician screens, which keeps the initial bundle small.
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const ReadingsHistory = lazy(() => import('./pages/ReadingsHistory'));
const LogReading = lazy(() => import('./pages/LogReading'));
const Trend = lazy(() => import('./pages/Trend'));
const Lifestyle = lazy(() => import('./pages/Lifestyle'));
const Alerts = lazy(() => import('./pages/Alerts'));
const ClinicianDashboard = lazy(() => import('./pages/ClinicianDashboard'));
const ClinicianPatientDetail = lazy(() => import('./pages/ClinicianPatientDetail'));
const ClinicianAlerts = lazy(() => import('./pages/ClinicianAlerts'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));

const PATIENT = ['patient'];
const CLINICIAN = ['clinician'];
const ADMIN = ['admin'];

function PrivateRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) return <Loader className="py-5" label="Checking your session" />;
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={roleHome(user.role)} replace />;
  }
  return children;
}

/** Sends an already-authenticated user straight to their own home screen. */
function PublicOnlyRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loader className="py-5" label="Checking your session" />;
  return user ? <Navigate to={roleHome(user.role)} replace /> : children;
}

function protectedRoute(path, element, allowedRoles) {
  return (
    <Route
      key={path}
      path={path}
      element={<PrivateRoute allowedRoles={allowedRoles}>{element}</PrivateRoute>}
    />
  );
}

function AppRoutes() {
  return (
    <Suspense fallback={<Loader className="py-5" />}>
      <Routes>
        <Route path="/login" element={<PublicOnlyRoute><Login /></PublicOnlyRoute>} />
        <Route path="/register" element={<PublicOnlyRoute><Register /></PublicOnlyRoute>} />

        {protectedRoute('/dashboard', <Dashboard />, PATIENT)}
        {protectedRoute('/readings', <ReadingsHistory />, PATIENT)}
        {protectedRoute('/readings/new', <LogReading />, PATIENT)}
        {protectedRoute('/trend', <Trend />, PATIENT)}
        {protectedRoute('/lifestyle', <Lifestyle />, PATIENT)}
        {protectedRoute('/alerts', <Alerts />, PATIENT)}

        {protectedRoute('/clinician', <ClinicianDashboard />, CLINICIAN)}
        {protectedRoute('/clinician/patients/:patientId', <ClinicianPatientDetail />, CLINICIAN)}
        {protectedRoute('/clinician/alerts', <ClinicianAlerts />, CLINICIAN)}

        {protectedRoute('/admin', <AdminDashboard />, ADMIN)}

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ConfirmProvider>
          <AuthProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </AuthProvider>
        </ConfirmProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
