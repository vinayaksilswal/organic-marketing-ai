import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { API_BASE } from '../config';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      setStatus({ type: 'error', message: 'Passwords do not match' });
      return;
    }
    if (password.length < 8) {
      setStatus({ type: 'error', message: 'Password must be at least 8 characters' });
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json();
      if (res.ok) {
        setStatus({ type: 'success', message: 'Password reset! Redirecting to login...' });
        setTimeout(() => navigate('/auth'), 2000);
      } else {
        setStatus({ type: 'error', message: data.detail || 'Reset failed' });
      }
    } catch (err) {
      setStatus({ type: 'error', message: 'Network error' });
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary, #0a0a0a)', color: '#fff' }}>
        <div style={{ textAlign: 'center', maxWidth: 400, padding: '2rem' }}>
          <h2>Invalid Reset Link</h2>
          <p style={{ color: '#999' }}>This password reset link is invalid or has expired.</p>
          <button onClick={() => navigate('/auth')} style={{ marginTop: '1rem', padding: '0.75rem 2rem', background: '#7c3aed', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary, #0a0a0a)', color: '#fff' }}>
      <form onSubmit={handleSubmit} style={{ maxWidth: 400, width: '100%', padding: '2rem' }}>
        <h2 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>Reset Password</h2>

        {status && (
          <div style={{ padding: '0.75rem', marginBottom: '1rem', borderRadius: 8, background: status.type === 'success' ? '#065f46' : '#7f1d1d', color: '#fff', fontSize: '0.9rem' }}>
            {status.message}
          </div>
        )}

        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#ccc' }}>New Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          style={{ width: '100%', padding: '0.75rem', marginBottom: '1rem', background: '#1a1a2e', border: '1px solid #333', borderRadius: 8, color: '#fff', fontSize: '1rem' }}
        />

        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', color: '#ccc' }}>Confirm Password</label>
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          minLength={8}
          style={{ width: '100%', padding: '0.75rem', marginBottom: '1.5rem', background: '#1a1a2e', border: '1px solid #333', borderRadius: 8, color: '#fff', fontSize: '1rem' }}
        />

        <button
          type="submit"
          disabled={loading}
          style={{ width: '100%', padding: '0.75rem', background: '#7c3aed', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontSize: '1rem', opacity: loading ? 0.7 : 1 }}
        >
          {loading ? 'Resetting...' : 'Reset Password'}
        </button>
      </form>
    </div>
  );
}
