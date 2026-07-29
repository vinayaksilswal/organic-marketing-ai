import React, { useState, useEffect } from 'react';
import { AlertTriangle, X, RefreshCw } from 'lucide-react';
import { API_BASE } from '../config';

const PUBLIC_API = API_BASE.replace('/api/v1', '');

/**
 * Surfaces backend problems instead of letting the dashboard fail silently.
 *
 * Two distinct failure modes are worth telling the user apart:
 *  - unreachable: the API is down or asleep entirely
 *  - degraded:    the API answers /health but is serving a build without the
 *                 endpoints this UI depends on, so features 404 for no visible
 *                 reason. This is the deploy-drift case.
 */
export default function SystemBanner() {
  const [state, setState] = useState(null); // null | 'unreachable' | 'degraded'
  const [detail, setDetail] = useState('');
  const [dismissed, setDismissed] = useState(false);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    setChecking(true);
    try {
      const res = await fetch(`${PUBLIC_API}/health`, { cache: 'no-store' });
      if (!res.ok) {
        setState('unreachable');
        setDetail(`The API responded with ${res.status}.`);
        return;
      }
      const health = await res.json().catch(() => ({}));

      // Detect a stale build from /health alone. This previously probed
      // /api/v1/team, which requires an X-Workspace-Id header the banner has
      // no business knowing — so every poll logged a 400 in the console, once
      // a minute, forever. /health reports the running commit and integration
      // status and needs no auth or workspace context.
      if (!health.commit || health.commit === 'unknown' || !health.integrations) {
        setState('degraded');
        setDetail('The server is running an older build that is missing features this page needs.');
        return;
      }

      setState(null);
      setDetail('');
    } catch {
      setState('unreachable');
      setDetail('The API could not be reached. It may be starting up.');
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    check();
    const id = setInterval(check, 60000);
    return () => clearInterval(id);
  }, []);

  if (!state || dismissed) return null;

  const unreachable = state === 'unreachable';

  return (
    <div
      role="status"
      style={{
        display: 'flex', alignItems: 'center', gap: '0.75rem',
        padding: '0.7rem 1.15rem',
        background: unreachable ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
        borderBottom: `1px solid ${unreachable ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'}`,
        color: unreachable ? '#fca5a5' : '#fcd34d',
        fontSize: '0.85rem',
      }}
    >
      <AlertTriangle size={16} style={{ flexShrink: 0 }} />
      <div style={{ flex: 1, lineHeight: 1.45 }}>
        <strong>{unreachable ? 'Backend unavailable' : 'Backend out of date'}</strong>
        {' — '}{detail}
        {unreachable && ' Free-tier servers sleep when idle; the first request can take up to a minute.'}
      </div>
      <button
        onClick={check}
        disabled={checking}
        title="Re-check"
        style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex', padding: '0.2rem', opacity: checking ? 0.5 : 1 }}
      >
        <RefreshCw size={15} style={checking ? { animation: 'spin 1s linear infinite' } : undefined} />
      </button>
      <button
        onClick={() => setDismissed(true)}
        title="Dismiss"
        style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex', padding: '0.2rem' }}
      >
        <X size={15} />
      </button>
    </div>
  );
}
