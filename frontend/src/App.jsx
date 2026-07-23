import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Onboarding from './pages/Onboarding';
import DashboardLayout from './pages/DashboardLayout';
import Checkout from './pages/Checkout';
import Toast from './components/Toast';
import { WorkspaceProvider } from './components/WorkspaceContext';

export const API_BASE = import.meta.env.VITE_API_URL || 'https://organic-marketing-ai1.onrender.com/api/v1';

/**
 * Helper: make authenticated API requests with automatic 401 handling.
 * Redirects to login on expired/invalid tokens instead of showing cryptic errors.
 */
export const authFetch = async (url, options = {}, token, onLogout) => {
  const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {}),
    ...(options.headers || {}),
  };

  try {
    const res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      // Token expired or invalid — auto-logout
      if (onLogout) onLogout();
      throw new Error('Session expired. Please log in again.');
    }

    return res;
  } catch (err) {
    // Network errors
    if (err.message === 'Session expired. Please log in again.') throw err;
    throw new Error('Network error. Please check your connection.');
  }
};

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
    if (user && user.subscriptionStatus !== "ACTIVE") return <Navigate to="/checkout" />;
    return <Component user={user} token={token} showToast={showToast} onLogout={handleLogout} updateAuth={(data) => {
      setUser(data);
      localStorage.setItem('user', JSON.stringify(data));
    }} />;
  };

  return (
    <>
      {toastMessage && <Toast message={toastMessage.message} isError={toastMessage.isError} />}
      
      <WorkspaceProvider token={token} onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<Auth onLogin={handleLogin} showToast={showToast} />} />
          <Route path="/checkout" element={token ? <Checkout user={user} onLogout={handleLogout} /> : <Navigate to="/auth" />} />
          <Route path="/onboarding" element={requireAuth(Onboarding)} />
          <Route path="/dashboard/*" element={requireAuth(DashboardLayout)} />
        </Routes>
      </WorkspaceProvider>
    </>
  );
}

export default App;
