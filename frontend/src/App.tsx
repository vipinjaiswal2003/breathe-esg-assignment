import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/Login';
import { DashboardPage } from './pages/Dashboard';
import { IngestionPage } from './pages/Ingestion';
import { ReviewQueuePage } from './pages/ReviewQueue';
import { EmissionDetailPage } from './pages/EmissionDetail';
import { AuditLogPage } from './pages/AuditLog';
import { EmissionFactorsPage } from './pages/EmissionFactors';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/ingest" element={<IngestionPage />} />
            <Route path="/review" element={<ReviewQueuePage />} />
            <Route path="/review/:id" element={<EmissionDetailPage />} />
            <Route path="/audit" element={<AuditLogPage />} />
            <Route path="/factors" element={<EmissionFactorsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
