import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Onboarding from './pages/Onboarding';
import DashboardLayout from './pages/DashboardLayout';
import Legal from './pages/Legal';
import Checkout from './pages/Checkout';
import ResetPassword from './pages/ResetPassword';
import Toast from './components/Toast';
import { WorkspaceProvider } from './components/WorkspaceContext';
import CookieBanner from './components/CookieBanner';
import UpgradeGate from './components/UpgradeGate';

export { API_BASE, authFetch } from './config';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  const [user, setUser] = useState(JSON.parse(localStorage.getItem('user') || 'null'));
  const [toastMessage, setToastMessage] = useState(null);
  const navigate = useNavigate();

  const showToast = (message, isError = false) => {
    setToastMessage({ message, isError });
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleLogin = (newToken, userData) => {
    setToken(newToken);
    setUser(userData);
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(userData));
    showToast('Welcome back!');
  };

  const handleLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/');
  }, [navigate]);

  useEffect(() => {
    if (token && !user?.subscriptionStatus) {
      // Re-fetch user to check onboarding/subscription status if incomplete
      authFetch(`${API_BASE}/users/me`, {}, token, handleLogout)
        .then(res => {
          if (!res.ok) throw new Error('Failed to fetch user');
          return res.json();
        })
        .then(data => {
          setUser(data);
          localStorage.setItem('user', JSON.stringify(data));
        })
        .catch(err => {
          console.error('Failed to fetch user', err);
          handleLogout();
        });
    }
  }, [token, handleLogout]);

  const requireAuth = (Component) => {
    if (!token) return <Navigate to="/auth" />;
    // A signed-in user reaches the product. Full stop.
    //
    // This used to bounce anyone whose subscriptionStatus was not "ACTIVE"
    // straight to /checkout — and new accounts are created INACTIVE, so the
    // free plan advertised on the landing page could not be reached at all.
    // Every visitor who pressed "Start free" met a payment wall instead of
    // the product, which is the worst possible outcome for paid traffic.
    //
    // The free plan is not enforced by locking the door. It is enforced by
    // the quota checks in billing_service, which run server-side on the
    // actions that cost money — publishing, generating, emailing — and cannot
    // be bypassed from the client. Letting someone in to hit a limit later is
    // how a free tier is supposed to work; the limit is the upsell.
    return <Component user={user} token={token} showToast={showToast} onLogout={handleLogout} updateAuth={(data) => {
      setUser(data);
      localStorage.setItem('user', JSON.stringify(data));
    }} />;
  };

  return (
    <>
      {toastMessage && <Toast message={toastMessage.message} isError={toastMessage.isError} />}
      
      <WorkspaceProvider token={token} onLogout={handleLogout}>
        <CookieBanner />
        <UpgradeGate />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<Navigate to="/dashboard" replace />} />
          <Route path="/privacy" element={<Legal title="Privacy Policy" />} />
          <Route path="/terms" element={<Legal title="Terms of Service" />} />
          <Route path="/dpa" element={<Legal title="Data Processing Agreement" />} />
          <Route path="/auth" element={<Auth onLogin={handleLogin} showToast={showToast} />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/checkout" element={token ? <Checkout user={user} onLogout={handleLogout} /> : <Navigate to="/auth" />} />
          <Route path="/onboarding" element={requireAuth(Onboarding)} />
          <Route path="/dashboard/*" element={requireAuth(DashboardLayout)} />
        </Routes>
      </WorkspaceProvider>
    </>
  );
}

export default App;
