import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, ArrowLeft } from 'lucide-react';
import { API_BASE } from '../App';

const Auth = ({ onLogin, showToast }) => {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    if (!isLoginMode && password.length < 8) {
      showToast('Password must be at least 8 characters', true);
      setLoading(false);
      return;
    }

    try {
      const endpoint = isLoginMode ? '/auth/login' : '/auth/register';
      const payload = JSON.stringify({ email, password });
        
      let res;
      let retries = 12; // Wait up to 60 seconds (12 * 5s) for Render server to wake up
      while (retries > 0) {
        try {
          res = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload
          });
          break; // Fetch successful (whether 200 or 401 etc), exit retry loop
        } catch (fetchErr) {
          if (fetchErr.name === 'TypeError' && fetchErr.message === 'Failed to fetch' && retries > 1) {
            showToast('Waking up server instance... Please wait, retrying automatically.', true);
            await new Promise(resolve => setTimeout(resolve, 5000));
            retries--;
          } else {
            throw fetchErr;
          }
        }
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || 'Authentication failed');
      }

      const data = await res.json();
      if (!data.success) {
         throw new Error(data.message || 'Authentication failed');
      }

      const token = data.token;
      
      let userRes;
      let userRetries = 3;
      while (userRetries > 0) {
        try {
          userRes = await fetch(`${API_BASE}/users/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          break;
        } catch (userErr) {
          if (userErr.name === 'TypeError' && userErr.message === 'Failed to fetch' && userRetries > 1) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            userRetries--;
          } else {
            throw userErr;
          }
        }
      }

      if (userRes && userRes.ok) {
        const userData = await userRes.json();
        onLogin(token, userData);
        
        if (!userData.businessProfile || userData.subscriptionStatus !== 'ACTIVE') {
          navigate('/onboarding');
        } else {
          navigate('/dashboard');
        }
      } else {
         throw new Error('Failed to fetch user data');
      }
    } catch (err) {
      if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
        showToast('Server is currently unreachable. Please check your internet connection.', true);
      } else {
        showToast(err.message || 'Authentication failed', true);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view centered-layout" style={{ position: 'relative' }}>
      
      {/* Background Decor */}
      <div style={{ position: 'absolute', top: '10%', left: '20%', width: '300px', height: '300px', background: 'var(--primary-color)', filter: 'blur(100px)', opacity: '0.2', borderRadius: '50%', zIndex: -1 }}></div>
      <div style={{ position: 'absolute', bottom: '10%', right: '20%', width: '400px', height: '400px', background: 'var(--secondary-color)', filter: 'blur(120px)', opacity: '0.15', borderRadius: '50%', zIndex: -1 }}></div>

      <div className="glass-panel card" style={{ padding: '3.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '2rem' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '1rem', borderRadius: '50%', border: '1px solid rgba(139, 92, 246, 0.2)' }}>
            <Sparkles size={32} color="var(--primary-color)" />
          </div>
        </div>

        <h2 style={{ textAlign: 'center', marginBottom: '0.5rem' }}>{isLoginMode ? 'Welcome back' : 'Create an account'}</h2>
        <p style={{ textAlign: 'center', marginBottom: '2.5rem', fontSize: '1.125rem' }}>
          {isLoginMode ? 'Enter your details to access your dashboard.' : 'Start automating your organic marketing today.'}
        </p>
        
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>Email Address</label>
            <input 
              type="email" 
              required 
              placeholder="you@example.com" 
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>
          <div className="input-group">
            <label>Password</label>
            <input 
              type="password" 
              required 
              placeholder="••••••••" 
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '1rem', marginTop: '1rem', fontSize: '1.125rem' }} disabled={loading}>
            <span>{isLoginMode ? 'Sign In' : 'Sign Up'}</span>
            {!loading ? <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} /> : <span className="spinner"></span>}
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', margin: '2rem 0' }}>
          <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color)' }}></div>
          <span style={{ padding: '0 1rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>or continue with</span>
          <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color)' }}></div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', flexDirection: 'column' }}>
          <button 
            type="button" 
            className="btn btn-secondary" 
            style={{ width: '100%', padding: '0.875rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)' }}
            onClick={() => showToast('Google SSO is not configured yet.', true)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Google
          </button>
          <button 
            type="button" 
            className="btn btn-secondary" 
            style={{ width: '100%', padding: '0.875rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', backgroundColor: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)' }}
            onClick={() => showToast('Microsoft SSO is not configured yet.', true)}
          >
            <svg width="20" height="20" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
              <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
              <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
              <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
              <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
            </svg>
            Microsoft
          </button>
        </div>

        <div style={{ textAlign: 'center', marginTop: '2rem', borderTop: '1px solid var(--border-color)', paddingTop: '2rem' }}>
          <p style={{ margin: 0, fontSize: '0.95rem' }}>
            {isLoginMode ? "Don't have an account? " : "Already have an account? "}
            <a 
              href="#" 
              onClick={(e) => { e.preventDefault(); setIsLoginMode(!isLoginMode); }} 
              style={{ color: 'var(--primary-color)', textDecoration: 'none', fontWeight: '600' }}
            >
              {isLoginMode ? 'Sign up for $17/mo' : 'Sign in'}
            </a>
          </p>
        </div>
      </div>

      <button 
        className="btn btn-secondary" 
        style={{ position: 'absolute', top: '2rem', left: '2rem', padding: '0.5rem 1rem', background: 'transparent', border: 'none' }}
        onClick={() => navigate('/')}
      >
        <ArrowLeft size={20} style={{ marginRight: '0.5rem' }} /> Back to Home
      </button>
    </div>
  );
};

export default Auth;
