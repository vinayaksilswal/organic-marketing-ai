import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE, authFetch } from '../../config';
import {
  CreditCard, Check, AlertTriangle, RefreshCw, Zap, ExternalLink,
} from 'lucide-react';

/**
 * Billing — plan, recurring PayPal subscription, and this month's usage.
 *
 * Entitlement is never granted here. Subscribing hands the user to PayPal;
 * access is only written server-side once PayPal's webhook confirms the money
 * moved, so a user who closes the approval window gets nothing.
 */
const Billing = ({ user, token, showToast }) => {
  const [plans, setPlans] = useState([]);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyPlan, setBusyPlan] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [planRes, meRes] = await Promise.all([
        authFetch(`${API_BASE}/billing/plans`, {}, token),
        authFetch(`${API_BASE}/billing/me`, {}, token),
      ]);
      if (planRes.ok) setPlans((await planRes.json()).plans || []);
      if (meRes.ok) { setMe(await meRes.json()); setError(null); }
      else setError(`Could not load your billing details (error ${meRes.status}).`);
    } catch {
      setError('Could not reach the server to load billing.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  // Returning from PayPal approval: reconcile immediately rather than making
  // the customer wait for a webhook that may be seconds or minutes behind.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (!params.get('subscribed')) return;
    (async () => {
      try {
        const res = await authFetch(`${API_BASE}/billing/sync`, { method: 'POST' }, token);
        if (res.ok) {
          setMe(await res.json());
          showToast('Subscription confirmed. Welcome aboard.');
        }
      } catch { /* the page still shows current state */ }
      window.history.replaceState({}, '', window.location.pathname);
    })();
  }, [token, showToast]);

  const subscribe = async (code) => {
    setBusyPlan(code);
    try {
      const res = await authFetch(`${API_BASE}/billing/subscribe`, {
        method: 'POST',
        body: JSON.stringify({ planCode: code }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Could not start the subscription');
      if (!data.approveUrl) throw new Error('PayPal did not return an approval link');
      // Full navigation, not a popup — popups are blocked more often than not.
      window.location.href = data.approveUrl;
    } catch (err) {
      showToast(err.message, true);
      setBusyPlan(null);
    }
  };

  const cancel = async () => {
    if (!window.confirm(
      'Cancel your subscription? You keep access until the end of the period you have already paid for.'
    )) return;
    setCancelling(true);
    try {
      const res = await authFetch(`${API_BASE}/billing/cancel`, { method: 'POST' }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Could not cancel');
      showToast(data.message || 'Subscription cancelled.');
      await load();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setCancelling(false);
    }
  };

  const sub = me?.subscription || {};
  const currentCode = me?.plan?.code;

  const meter = (m) => {
    const u = me?.usage?.[m];
    if (!u) return null;
    const unlimited = u.limit === null || u.limit === undefined;
    const pct = unlimited ? 0 : Math.min(100, Math.round((u.used / Math.max(u.limit, 1)) * 100));
    const danger = !unlimited && pct >= 90;
    return (
      <div key={m} style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.83rem', marginBottom: '0.35rem' }}>
          <span style={{ textTransform: 'capitalize' }}>{u.label}</span>
          <span style={{ color: danger ? '#f87171' : 'var(--text-muted)' }}>
            {u.used.toLocaleString()}{unlimited ? ' · unlimited' : ` / ${u.limit.toLocaleString()}`}
          </span>
        </div>
        <div style={{ height: 6, borderRadius: 999, background: 'rgba(11, 16, 32, 0.07)', overflow: 'hidden' }}>
          <div style={{
            width: `${unlimited ? 4 : pct}%`, height: '100%', borderRadius: 999,
            background: danger ? '#ef4444' : 'linear-gradient(90deg, var(--primary-color), var(--secondary-color))',
          }} />
        </div>
      </div>
    );
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0', maxWidth: 1100 }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
            <CreditCard color="var(--primary-color)" size={28} /> Plan & Billing
          </h1>
          <p className="text-muted" style={{ margin: '0.3rem 0 0 0', fontSize: '0.95rem' }}>
            Billed monthly through PayPal. Cancel any time — access runs to the end of the period you paid for.
          </p>
        </div>

        {loading ? (
          <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
            <span className="spinner" style={{ width: 22, height: 22 }} />
          </div>
        ) : error ? (
          <div className="glass-panel" style={{ padding: '2.5rem', textAlign: 'center' }}>
            <AlertTriangle size={22} color="#f87171" />
            <p style={{ color: '#fca5a5', margin: '0.7rem 0 1rem' }}>{error}</p>
            <button className="btn btn-secondary" onClick={load}>Retry</button>
          </div>
        ) : (
          <>
            {/* CURRENT STATE */}
            <div className="glass-panel" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 260px' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
                    Current plan
                  </span>
                  <h2 style={{ margin: '0.3rem 0 0.2rem', fontSize: '1.65rem' }}>{me?.plan?.name}</h2>
                  <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                    {me?.plan?.price > 0 ? `$${me.plan.price}/month` : 'No card required'}
                  </p>

                  {sub.status === 'ACTIVE' && sub.currentPeriodEnd && (
                    <p style={{ margin: '0.7rem 0 0', fontSize: '0.83rem', color: 'var(--text-muted)' }}>
                      {sub.cancelAtPeriodEnd ? 'Access ends' : 'Renews'} on{' '}
                      {new Date(sub.currentPeriodEnd).toLocaleDateString()}
                    </p>
                  )}
                  {sub.status === 'APPROVAL_PENDING' && (
                    <p style={{ margin: '0.7rem 0 0', fontSize: '0.83rem', color: '#fbbf24' }}>
                      Waiting for PayPal approval. If you already approved it, press Refresh.
                    </p>
                  )}
                  {sub.lastError && (
                    <div style={{ marginTop: '0.8rem', padding: '0.6rem 0.75rem', borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)' }}>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: '#fca5a5', lineHeight: 1.5 }}>
                        {sub.lastError}
                      </p>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '0.6rem', marginTop: '1.1rem', flexWrap: 'wrap' }}>
                    <button className="btn btn-secondary" onClick={load}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.45rem 0.9rem', fontSize: '0.83rem' }}>
                      <RefreshCw size={14} /> Refresh
                    </button>
                    {sub.status === 'ACTIVE' && !sub.cancelAtPeriodEnd && (
                      <button className="btn btn-secondary" onClick={cancel} disabled={cancelling}
                        style={{ padding: '0.45rem 0.9rem', fontSize: '0.83rem', color: 'var(--error)' }}>
                        {cancelling ? 'Cancelling…' : 'Cancel subscription'}
                      </button>
                    )}
                  </div>
                </div>

                <div style={{ flex: '1 1 320px' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
                    This month · {me?.period}
                  </span>
                  <div style={{ marginTop: '0.9rem' }}>
                    {['posts', 'prompts', 'emails', 'media'].map(meter)}
                  </div>
                </div>
              </div>
            </div>

            {/* PLANS */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem' }}>
              {plans.map(p => {
                const isCurrent = p.code === currentCode;
                const isFree = p.price <= 0;
                return (
                  <div key={p.code} className="glass-panel" style={{
                    padding: '1.6rem', display: 'flex', flexDirection: 'column',
                    border: isCurrent ? '1px solid var(--primary-color)' : undefined,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <h3 style={{ margin: 0, fontSize: '1.15rem' }}>{p.name}</h3>
                      {isCurrent && (
                        <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: 4, background: 'rgba(139,92,246,0.18)', color: 'var(--primary-color)' }}>
                          CURRENT
                        </span>
                      )}
                    </div>
                    <div style={{ margin: '0.6rem 0 0.15rem', fontSize: '1.9rem', fontWeight: 700 }}>
                      {isFree ? 'Free' : `$${p.price}`}
                      {!isFree && <span style={{ fontSize: '0.85rem', fontWeight: 400, color: 'var(--text-muted)' }}>/mo</span>}
                    </div>
                    <p style={{ margin: '0 0 1rem', fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      {p.tagline}
                    </p>

                    <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1.4rem', display: 'grid', gap: '0.5rem', flex: 1 }}>
                      {p.features.map(f => (
                        <li key={f} style={{ display: 'flex', gap: '0.45rem', fontSize: '0.83rem', lineHeight: 1.45 }}>
                          <Check size={14} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
                          {f}
                        </li>
                      ))}
                    </ul>

                    {isCurrent ? (
                      <button className="btn btn-secondary" disabled style={{ opacity: 0.6 }}>
                        Your plan
                      </button>
                    ) : isFree ? (
                      <button className="btn btn-secondary" disabled style={{ opacity: 0.6 }}>
                        Included
                      </button>
                    ) : (
                      <button className="btn btn-primary" onClick={() => subscribe(p.code)} disabled={busyPlan === p.code}
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.45rem' }}>
                        {busyPlan === p.code
                          ? <><span className="spinner" style={{ width: 13, height: 13 }} /> Opening PayPal…</>
                          : <><Zap size={15} /> Choose {p.name}</>}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            <p style={{ marginTop: '1.5rem', fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <ExternalLink size={13} />
              Payments are handled entirely by PayPal. We never see or store your card details.
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export default Billing;
