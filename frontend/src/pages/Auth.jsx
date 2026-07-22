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
        
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || 'Authentication failed');
      }

      const data = await res.json();
      if (!data.success) {
         throw new Error(data.message || 'Authentication failed');
      }

      const token = data.token;
      
      const userRes = await fetch(`${API_BASE}/users/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (userRes.ok) {
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
        showToast('Waking up server instance... Please try again in 5 seconds.', true);
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
