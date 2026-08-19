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
  in_progress: { label: 'We are on it', colour: '#3b82f6', Icon: MessageSquare },
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

  return (
    <div className="container" style={{ padding: '2.5rem 0', maxWidth: 860 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', marginBottom: '0.4rem' }}>
        <LifeBuoy size={26} color="var(--primary-color)" />
        <h1 style={{ margin: 0 }}>Support</h1>
      </div>
      <p style={{ marginBottom: '2rem', color: 'var(--text-muted)' }}>
        Tell us what is wrong and we will fix it. Replies appear here, not in your inbox.
      </p>

      {/* Report */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.02rem', marginBottom: '1rem' }}>Report something</h3>
        <form onSubmit={submitTicket}>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.9rem' }}>
            {CATEGORIES.map(([key, label]) => {
              const on = category === key;
              return (
                <button
                  key={key} type="button" onClick={() => setCategory(key)} aria-pressed={on}
                  style={{
                    minHeight: 40, padding: '0 0.85rem', borderRadius: 9, cursor: 'pointer',
                    fontWeight: 650, fontSize: '0.84rem',
                    background: on ? 'var(--primary-color)' : 'rgba(11,16,32,0.04)',
                    color: on ? '#fff' : 'var(--text-main)',
                    border: `1px solid ${on ? 'var(--primary-color)' : 'var(--border-color)'}`,
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <input
            value={subject} onChange={(e) => setSubject(e.target.value)}
            placeholder="One line: what happened?"
            style={{
              width: '100%', minHeight: 44, padding: '0.7rem 0.85rem', marginBottom: '0.7rem',
              borderRadius: 10, border: '1px solid var(--border-color)', fontSize: '0.95rem',
            }}
          />
          <textarea
            value={body} onChange={(e) => setBody(e.target.value)}
            placeholder="What were you doing, what did you expect, and what happened instead? Workspace name helps."
            rows={5}
            style={{
              width: '100%', padding: '0.7rem 0.85rem', marginBottom: '0.9rem',
              borderRadius: 10, border: '1px solid var(--border-color)',
              fontSize: '0.95rem', fontFamily: 'inherit', resize: 'vertical',
            }}
          />
          <button
            type="submit" className="btn btn-primary" disabled={sending}
            style={{ minHeight: 44, display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {sending ? <span className="spinner" style={{ width: 15, height: 15 }} /> : <Send size={16} />}
            {sending ? 'Sending…' : 'Send'}
          </button>
        </form>
      </div>

      {/* History */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.02rem', marginBottom: '1rem' }}>Your reports</h3>
        {loading ? (
          <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>Loading…</p>
        ) : !tickets.length ? (
          <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
            Nothing reported yet.
          </p>
        ) : tickets.map((t) => {
          const look = STATUS_LOOK[t.status] || STATUS_LOOK.open;
          const { Icon } = look;
          return (
            <div key={t.id} style={{
              border: '1px solid var(--border-color)', borderRadius: 11,
              padding: '0.9rem', marginBottom: '0.7rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
                <Icon size={15} color={look.colour} />
                <span style={{ fontWeight: 700, fontSize: '0.92rem' }}>{t.subject}</span>
                <span style={{
                  fontSize: '0.7rem', fontWeight: 800, letterSpacing: '.05em',
                  textTransform: 'uppercase', color: look.colour,
                }}>{look.label}</span>
                <span style={{ marginLeft: 'auto', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                  {t.createdAt ? new Date(t.createdAt).toLocaleDateString() : ''}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{t.body}</p>
              {t.reply && (
                <div style={{
                  marginTop: '0.75rem', padding: '0.7rem 0.85rem', borderRadius: 9,
                  background: 'rgba(109,40,217,0.06)', border: '1px solid rgba(109,40,217,0.18)',
                }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 800, letterSpacing: '.05em', textTransform: 'uppercase', color: 'var(--primary-color)', marginBottom: '0.3rem' }}>
                    Our reply
                  </div>
                  <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{t.reply}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Review */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '1.02rem', marginBottom: '0.4rem' }}>How is it going?</h3>
        <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
          {review?.isApproved
            ? 'Your review is published. Contact support to change it.'
            : 'We read every one of these. Nothing is shown publicly unless we ask you first.'}
        </p>

        <div style={{ display: 'flex', gap: '0.3rem', marginBottom: '0.9rem' }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n} type="button" aria-label={`${n} star${n > 1 ? 's' : ''}`}
              onClick={() => !review?.isApproved && setRating(n)}
              disabled={review?.isApproved}
              style={{
                width: 44, height: 44, borderRadius: 10, cursor: review?.isApproved ? 'default' : 'pointer',
                background: 'transparent', border: '1px solid var(--border-color)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <Star size={19} color={n <= rating ? '#f59e0b' : 'var(--text-muted)'}
                    fill={n <= rating ? '#f59e0b' : 'none'} />
            </button>
          ))}
        </div>

        <textarea
          value={reviewBody} onChange={(e) => setReviewBody(e.target.value)}
          disabled={review?.isApproved}
          placeholder="What is it doing for you? Specifics help more than praise."
          rows={3}
          style={{
            width: '100%', padding: '0.7rem 0.85rem', marginBottom: '0.9rem',
            borderRadius: 10, border: '1px solid var(--border-color)',
            fontSize: '0.95rem', fontFamily: 'inherit', resize: 'vertical',
          }}
        />
        {!review?.isApproved && (
          <button onClick={submitReview} className="btn btn-primary" disabled={savingReview}
                  style={{ minHeight: 44 }}>
            {savingReview ? 'Saving…' : review ? 'Update review' : 'Send review'}
          </button>
        )}
      </div>
    </div>
  );
};

export default Support;
