import React, { useCallback, useEffect, useState } from 'react';
import { Inbox, Star, Send, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { API_BASE, authFetch } from '../../config';

/**
 * The operator's side of support: read a report, answer it, close it.
 *
 * The endpoints existed without this page, which meant the only way to answer
 * a customer was to write a curl command — so in practice nobody would have
 * been answered at all.
 *
 * Reachable only by a super-admin. The API answers 404 rather than 403 to
 * everyone else, so a non-admin who guesses the URL simply sees an empty page
 * rather than confirmation that an admin area exists.
 */

const STATUSES = ['open', 'in_progress', 'resolved'];
const STATUS_COLOUR = { open: '#f59e0b', in_progress: 'var(--secondary-color)', resolved: '#059669' };

const AdminSupport = ({ showToast, token }) => {
  const [tab, setTab] = useState('tickets');
  const [tickets, setTickets] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [filter, setFilter] = useState('open');
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [drafts, setDrafts] = useState({});
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filter === 'all' ? '' : `?status=${filter}`;
      const [t, r] = await Promise.all([
        authFetch(`${API_BASE}/support/admin/tickets${qs}`, {}, token),
        authFetch(`${API_BASE}/support/admin/reviews`, {}, token),
      ]);
      if (t.status === 404) { setDenied(true); return; }
      if (t.ok) setTickets((await t.json()).tickets || []);
      if (r.ok) setReviews((await r.json()).reviews || []);
    } catch {
      /* nothing to show is better than a crash */
    } finally {
      setLoading(false);
    }
  }, [filter, token]);

  useEffect(() => { load(); }, [load]);

  const patchTicket = async (id, payload) => {
    setBusy(id);
    try {
      const res = await authFetch(`${API_BASE}/support/admin/tickets/${id}`, {
        method: 'PATCH', body: JSON.stringify(payload),
      }, token);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast('Sent to the customer.');
      setDrafts((d) => ({ ...d, [id]: '' }));
      await load();
    } catch (err) {
      showToast(`Could not update that — ${err.message}`, true);
    } finally {
      setBusy(null);
    }
  };

  const setApproval = async (id, approve) => {
    setBusy(id);
    try {
      const res = await authFetch(
        `${API_BASE}/support/admin/reviews/${id}?approve=${approve}`,
        { method: 'PATCH' }, token
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast(approve ? 'Published to the landing page.' : 'Hidden.');
      await load();
    } catch (err) {
      showToast(`Could not update that — ${err.message}`, true);
    } finally {
      setBusy(null);
    }
  };

  if (denied) {
    return (
      <div className="container" style={{ padding: '3rem 0', maxWidth: 640 }}>
        <p style={{ color: 'var(--text-muted)' }}>Nothing here.</p>
      </div>
    );
  }

  const chip = (on) => ({
    minHeight: 38, padding: '0 0.8rem', borderRadius: 10, cursor: 'pointer',
    fontSize: '0.82rem', fontWeight: 600,
    background: on ? 'var(--primary-color)' : 'rgba(11,16,32,0.04)',
    color: on ? '#fff' : 'var(--text-main)',
    border: `1px solid ${on ? 'var(--primary-color)' : 'var(--border-color)'}`,
  });

  return (
    <div className="container" style={{ padding: '2.5rem 0', maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', marginBottom: '1.5rem' }}>
        <Inbox size={25} color="var(--primary-color)" />
        <h1 style={{ margin: 0 }}>Support inbox</h1>
      </div>

      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <button onClick={() => setTab('tickets')} style={chip(tab === 'tickets')}>
          Tickets ({tickets.length})
        </button>
        <button onClick={() => setTab('reviews')} style={chip(tab === 'reviews')}>
          Reviews ({reviews.filter((r) => !r.isApproved).length} waiting)
        </button>
      </div>

      {tab === 'tickets' && (
        <>
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            {['open', 'in_progress', 'resolved', 'all'].map((f) => (
              <button key={f} onClick={() => setFilter(f)} style={chip(filter === f)}>
                {f.replace('_', ' ')}
              </button>
            ))}
          </div>

          {loading ? <p style={{ color: 'var(--text-muted)' }}>Loading…</p>
            : !tickets.length ? <p style={{ color: 'var(--text-muted)' }}>Nothing here.</p>
            : tickets.map((t) => (
              <div key={t.id} className="glass-panel" style={{ padding: '1.2rem', marginBottom: '0.9rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 700 }}>{t.subject}</span>
                  <span style={{
                    fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase',
                    letterSpacing: '.05em', color: STATUS_COLOUR[t.status] || '#888',
                  }}>{t.status.replace('_', ' ')}</span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{t.category}</span>
                  <span style={{ marginLeft: 'auto', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    {t.userEmail}
                  </span>
                </div>

                <p style={{ margin: '0 0 0.8rem', fontSize: '0.87rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                  {t.body}
                </p>

                {t.reply && (
                  <div style={{
                    padding: '0.6rem 0.8rem', borderRadius: 10, marginBottom: '0.7rem',
                    background: 'rgba(5,150,105,0.07)', border: '1px solid rgba(5,150,105,0.2)',
                  }}>
                    <div style={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--success)', marginBottom: '0.25rem' }}>
                      Replied
                    </div>
                    <p style={{ margin: 0, fontSize: '0.84rem', whiteSpace: 'pre-wrap' }}>{t.reply}</p>
                  </div>
                )}

                <textarea
                  value={drafts[t.id] ?? ''}
                  onChange={(e) => setDrafts((d) => ({ ...d, [t.id]: e.target.value }))}
                  placeholder={t.reply ? 'Replace the reply…' : 'Reply to this customer…'}
                  rows={3}
                  style={{
                    width: '100%', padding: '0.6rem 0.75rem', borderRadius: 10,
                    border: '1px solid var(--border-color)', fontSize: '0.9rem',
                    fontFamily: 'inherit', resize: 'vertical', marginBottom: '0.6rem',
                  }}
                />

                <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => patchTicket(t.id, { reply: drafts[t.id] })}
                    disabled={busy === t.id || !(drafts[t.id] || '').trim()}
                    className="btn btn-primary"
                    style={{ minHeight: 40, display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                  >
                    <Send size={14} /> Send reply
                  </button>
                  {STATUSES.filter((sv) => sv !== t.status).map((sv) => (
                    <button key={sv} onClick={() => patchTicket(t.id, { status: sv })}
                            disabled={busy === t.id} style={{ ...chip(false), minHeight: 40 }}>
                      {sv === 'resolved' ? <><CheckCircle2 size={13} /> Resolve</> : `Mark ${sv.replace('_', ' ')}`}
                    </button>
                  ))}
                </div>
              </div>
            ))}
        </>
      )}

      {tab === 'reviews' && (
        loading ? <p style={{ color: 'var(--text-muted)' }}>Loading…</p>
        : !reviews.length ? <p style={{ color: 'var(--text-muted)' }}>No reviews yet.</p>
        : reviews.map((r) => (
          <div key={r.id} className="glass-panel" style={{ padding: '1.2rem', marginBottom: '0.9rem' }}>
            <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', marginBottom: '0.5rem' }}>
              {[1, 2, 3, 4, 5].map((n) => (
                <Star key={n} size={14} color={n <= r.rating ? '#f59e0b' : 'var(--text-muted)'}
                      fill={n <= r.rating ? '#f59e0b' : 'none'} />
              ))}
              <span style={{ marginLeft: 'auto', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                {[r.authorName, r.authorBusiness].filter(Boolean).join(' · ')}
              </span>
            </div>
            {r.body && (
              <p style={{ margin: '0 0 0.8rem', fontSize: '0.87rem', lineHeight: 1.6 }}>{r.body}</p>
            )}
            <button
              onClick={() => setApproval(r.id, !r.isApproved)}
              disabled={busy === r.id}
              className={r.isApproved ? '' : 'btn btn-primary'}
              style={r.isApproved
                ? { ...chip(false), minHeight: 40, display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }
                : { minHeight: 40, display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
            >
              {r.isApproved ? <><EyeOff size={14} /> Hide from landing page</> : <><Eye size={14} /> Publish</>}
            </button>
          </div>
        ))
      )}
    </div>
  );
};

export default AdminSupport;
