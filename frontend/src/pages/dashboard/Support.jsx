import React, { useCallback, useEffect, useState } from 'react';
import {
  LifeBuoy, Send, CheckCircle2, Clock, MessageSquare, Star,
} from 'lucide-react';
import { API_BASE, authFetch } from '../../config';

/**
 * Where a customer says something is broken, and says what they think.
 *
 * The reply lives on the ticket rather than in an inbox. Support answered by
 * email is invisible to everyone but the two people in the thread — the
 * customer cannot find it again and cannot see whether anything is happening.
 * Here the answer sits beside the question and the status is on the row.
 */

const CATEGORIES = [
  ['bug', 'Something is broken'],
  ['question', 'How do I…'],
  ['billing', 'Billing'],
  ['feature', 'Feature request'],
];

const STATUS_LOOK = {
  open: { label: 'Open', colour: '#f59e0b', Icon: Clock },
  in_progress: { label: 'We are on it', colour: 'var(--secondary-color)', Icon: MessageSquare },
  resolved: { label: 'Resolved', colour: '#059669', Icon: CheckCircle2 },
};

const Support = ({ token, showToast }) => {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const [category, setCategory] = useState('bug');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  const [review, setReview] = useState(null);
  const [rating, setRating] = useState(0);
  const [reviewBody, setReviewBody] = useState('');
  const [savingReview, setSavingReview] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, r] = await Promise.all([
        authFetch(`${API_BASE}/support/tickets`, {}, token),
        authFetch(`${API_BASE}/support/reviews/mine`, {}, token),
      ]);
      if (t.ok) setTickets((await t.json()).tickets || []);
      if (r.ok) {
        const mine = (await r.json()).review;
        if (mine) {
          setReview(mine);
          setRating(mine.rating || 0);
          setReviewBody(mine.body || '');
        }
      }
    } catch {
      /* the form still works even if the list will not load */
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const submitTicket = async (e) => {
    e.preventDefault();
    if (subject.trim().length < 3 || body.trim().length < 10) {
      return showToast('Add a subject and a little more detail.', true);
    }
    setSending(true);
    try {
      const res = await authFetch(`${API_BASE}/support/tickets`, {
        method: 'POST',
        body: JSON.stringify({ subject: subject.trim(), body: body.trim(), category }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Could not send that.');
      setSubject(''); setBody('');
      showToast('Sent. You will see the reply here.');
      await load();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSending(false);
    }
  };

  const submitReview = async () => {
    if (!rating) return showToast('Pick a rating first.', true);
    setSavingReview(true);
    try {
      const res = await authFetch(`${API_BASE}/support/reviews`, {
        method: 'POST',
        body: JSON.stringify({ rating, body: reviewBody.trim() || null }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Could not save that.');
      showToast(data.message || 'Thank you.');
      await load();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSavingReview(false);
    }
  };

  const [activeSupportTab, setActiveSupportTab] = useState('tickets'); // 'tickets' | 'reviews'

  return (
    <div className="container" style={{ padding: '2rem 0 3rem', maxWidth: 880 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', marginBottom: '0.3rem' }}>
            <LifeBuoy size={26} color="var(--primary-color)" />
            <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 800 }}>Support &amp; Reviews</h1>
          </div>
          <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.92rem' }}>
            Direct enterprise assistance, ticket tracking, and verified customer reviews.
          </p>
        </div>

        {/* Tab switcher */}
        <div style={{ display: 'flex', background: 'rgba(11,16,32,0.05)', padding: '0.25rem', borderRadius: 10, border: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setActiveSupportTab('tickets')}
            style={{
              padding: '0.45rem 0.95rem',
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '0.84rem',
              background: activeSupportTab === 'tickets' ? 'var(--primary-color)' : 'transparent',
              color: activeSupportTab === 'tickets' ? '#fff' : 'var(--text-muted)',
              transition: 'background 0.15s, color 0.15s',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <MessageSquare size={15} /> Support Tickets ({tickets.length})
          </button>
          <button
            onClick={() => setActiveSupportTab('reviews')}
            style={{
              padding: '0.45rem 0.95rem',
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '0.84rem',
              background: activeSupportTab === 'reviews' ? 'var(--primary-color)' : 'transparent',
              color: activeSupportTab === 'reviews' ? '#fff' : 'var(--text-muted)',
              transition: 'background 0.15s, color 0.15s',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <Star size={15} /> Reviews &amp; Rating {review?.rating ? `(${review.rating}★)` : ''}
          </button>
        </div>
      </div>

      {activeSupportTab === 'tickets' ? (
        <>
          {/* Report New Ticket */}
          <div className="glass-panel" style={{ padding: '1.75rem', marginBottom: '1.5rem', borderRadius: 14 }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.4rem' }}>Open a New Ticket</h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '1.1rem' }}>
              Report a bug, request a feature, or ask a question. Response SLA is under 24 hours.
            </p>
            <form onSubmit={submitTicket}>
              <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                {CATEGORIES.map(([key, label]) => {
                  const on = category === key;
                  return (
                    <button
                      key={key} type="button" onClick={() => setCategory(key)} aria-pressed={on}
                      style={{
                        minHeight: 38, padding: '0 0.85rem', borderRadius: 8, cursor: 'pointer',
                        fontWeight: 600, fontSize: '0.82rem',
                        background: on ? 'var(--primary-color)' : 'rgba(11,16,32,0.04)',
                        color: on ? '#fff' : 'var(--text-main)',
                        border: `1px solid ${on ? 'var(--primary-color)' : 'var(--border-color)'}`,
                        transition: 'background 0.15s, color 0.15s',
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>

              <input
                value={subject} onChange={(e) => setSubject(e.target.value)}
                placeholder="One line: what happened or what do you need?"
                style={{
                  width: '100%', minHeight: 44, padding: '0.7rem 0.85rem', marginBottom: '0.75rem',
                  borderRadius: 10, border: '1px solid var(--border-color)', fontSize: '0.92rem',
                  background: 'rgba(11, 16, 32, 0.03)', color: 'var(--text-main)',
                }}
              />
              <textarea
                value={body} onChange={(e) => setBody(e.target.value)}
                placeholder="What were you doing, what did you expect, and what happened instead? Workspace or account details help."
                rows={4}
                style={{
                  width: '100%', padding: '0.75rem 0.85rem', marginBottom: '1rem',
                  borderRadius: 10, border: '1px solid var(--border-color)',
                  fontSize: '0.92rem', fontFamily: 'inherit', resize: 'vertical',
                  background: 'rgba(11, 16, 32, 0.03)', color: 'var(--text-main)',
                }}
              />
              <button
                type="submit" className="btn btn-primary" disabled={sending}
                style={{ minHeight: 42, display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.25rem', fontWeight: 600 }}
              >
                {sending ? <span className="spinner" style={{ width: 15, height: 15 }} /> : <Send size={15} />}
                {sending ? 'Submitting…' : 'Submit Ticket'}
              </button>
            </form>
          </div>

          {/* Ticket History */}
          <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>Your Open &amp; Past Tickets</h3>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{tickets.length} total</span>
            </div>
            {loading ? (
              <div style={{ padding: '2.5rem', textAlign: 'center' }}><span className="spinner" style={{ width: 20, height: 20 }} /></div>
            ) : !tickets.length ? (
              <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                <CheckCircle2 size={24} color="#10b981" style={{ marginBottom: '0.5rem', opacity: 0.7 }} />
                <div>No active tickets. All systems operational.</div>
              </div>
            ) : tickets.map((t) => {
              const look = STATUS_LOOK[t.status] || STATUS_LOOK.open;
              const { Icon } = look;
              return (
                <div key={t.id} style={{
                  border: '1px solid var(--border-color)', borderRadius: 10,
                  padding: '1rem 1.15rem', marginBottom: '0.85rem', background: 'rgba(11, 16, 32, 0.02)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '0.45rem' }}>
                    <Icon size={16} color={look.colour} />
                    <span style={{ fontWeight: 800, fontSize: '0.94rem', color: 'var(--text-main)' }}>{t.subject}</span>
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 800, letterSpacing: '.04em',
                      textTransform: 'uppercase', color: look.colour, background: `${look.colour}18`,
                      padding: '0.15rem 0.5rem', borderRadius: 4,
                    }}>{look.label}</span>
                    <span style={{ marginLeft: 'auto', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                      {t.createdAt ? new Date(t.createdAt).toLocaleDateString() : ''}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.86rem', lineHeight: 1.55, whiteSpace: 'pre-wrap', color: 'var(--text-main)' }}>{t.body}</p>
                  {t.reply && (
                    <div style={{
                      marginTop: '0.85rem', padding: '0.85rem 1rem', borderRadius: 10,
                      background: 'rgba(109,40,217,0.06)', border: '1px solid rgba(109,40,217,0.2)',
                    }}>
                      <div style={{ fontSize: '0.72rem', fontWeight: 800, letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--primary-color)', marginBottom: '0.35rem' }}>
                        Support Team Response
                      </div>
                      <p style={{ margin: 0, fontSize: '0.86rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{t.reply}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        /* Customer Reviews & Feedback */
        <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: 14 }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.4rem' }}>Platform Review &amp; Feedback</h3>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.5 }}>
            {review?.isApproved
              ? 'Your verified review is live on our review wall. Contact support if you need to update it.'
              : 'Share your feedback and experience with Organiflo. We read every submission to improve the platform.'}
          </p>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n} type="button" aria-label={`${n} star${n > 1 ? 's' : ''}`}
                onClick={() => !review?.isApproved && setRating(n)}
                disabled={review?.isApproved}
                style={{
                  width: 44, height: 44, borderRadius: 10, cursor: review?.isApproved ? 'default' : 'pointer',
                  background: n <= rating ? 'rgba(245, 158, 11, 0.15)' : 'rgba(11, 16, 32, 0.04)',
                  border: `1px solid ${n <= rating ? '#f59e0b' : 'var(--border-color)'}`,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'transform 0.15s, background 0.15s',
                }}
                onMouseEnter={e => { if (!review?.isApproved) e.currentTarget.style.transform = 'scale(1.1)'; }}
                onMouseLeave={e => { if (!review?.isApproved) e.currentTarget.style.transform = 'none'; }}
              >
                <Star size={20} color={n <= rating ? '#f59e0b' : 'var(--text-muted)'}
                      fill={n <= rating ? '#f59e0b' : 'none'} />
              </button>
            ))}
            <span style={{ marginLeft: '0.5rem', fontWeight: 700, fontSize: '0.9rem', color: rating ? '#f59e0b' : 'var(--text-muted)' }}>
              {rating === 5 ? 'Exceptional (5/5)' : rating === 4 ? 'Great (4/5)' : rating === 3 ? 'Good (3/5)' : rating > 0 ? 'Needs Improvement' : 'Select a rating'}
            </span>
          </div>

          <textarea
            value={reviewBody} onChange={(e) => setReviewBody(e.target.value)}
            disabled={review?.isApproved}
            placeholder="What results or time savings has Organiflo delivered for your business? Specific feedback helps most."
            rows={4}
            style={{
              width: '100%', padding: '0.85rem', marginBottom: '1.1rem',
              borderRadius: 10, border: '1px solid var(--border-color)',
              fontSize: '0.92rem', fontFamily: 'inherit', resize: 'vertical',
              background: 'rgba(11, 16, 32, 0.03)', color: 'var(--text-main)',
            }}
          />
          {!review?.isApproved && (
            <button onClick={submitReview} className="btn btn-primary" disabled={savingReview || !rating}
                    style={{ minHeight: 42, padding: '0.6rem 1.35rem', fontWeight: 600 }}>
              {savingReview ? 'Saving…' : review ? 'Update Review' : 'Submit Review'}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default Support;
