import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Onboarding from './pages/Onboarding';
import Dashboard from './pages/Dashboard';
import Navbar from './components/Navbar';
import Toast from './components/Toast';

export const API_BASE = import.meta.env.VITE_API_URL || 'https://organic-marketing-ai1.onrender.com/api/v1';

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

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/');
  };

  useEffect(() => {
    if (token && !user?.subscriptionStatus) {
      // Re-fetch user to check onboarding/subscription status if incomplete
      fetch(`${API_BASE}/users/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      .then(res => res.json())
      .then(data => {
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data));
      })
      .catch(err => {
        console.error('Failed to fetch user', err);
        handleLogout();
      });
    }
  }, [token]);

  const requireAuth = (Component) => {
    if (!token) return <Navigate to="/auth" />;
    return <Component user={user} token={token} showToast={showToast} updateAuth={(data) => {
      setUser(data);
      localStorage.setItem('user', JSON.stringify(data));
    }} />;
  };

  return (
    <>
      {toastMessage && <Toast message={toastMessage.message} isError={toastMessage.isError} />}
      {(token && (user?.businessProfile && user?.subscriptionStatus === 'ACTIVE')) && <Navbar onLogout={handleLogout} />}
      
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/auth" element={<Auth onLogin={handleLogin} showToast={showToast} />} />
        <Route path="/onboarding" element={requireAuth(Onboarding)} />
        <Route path="/dashboard" element={requireAuth(Dashboard)} />
      </Routes>
    </>
  );
}

export default App;
