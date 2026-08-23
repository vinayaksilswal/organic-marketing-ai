import React, { useCallback, useEffect, useState } from 'react';
import { Inbox, ExternalLink, RefreshCw, CheckCircle2 } from 'lucide-react';
import { API_BASE, authFetch, apiError } from '../config';

/**
 * The people in your comments who were trying to buy something.
 *
 * Reach and engagement are proxies. This is the thing they are proxies for:
 * somebody asked what it costs, in public, and is waiting. Ordered by how
 * close they are to paying and whether anyone has replied yet, because the
 * unanswered price question is the most expensive item on the page.
 *
 * Every row shows the phrase that flagged it, so a wrong match is visibly
 * wrong rather than a verdict to be taken on trust.
 */

const KIND_LABEL = {
  price: 'Asked the price',
  buy: 'Asked how to buy',
  availability: 'Asked if available',
  contact: 'Wants contact',
  interest: 'Said they want it',
  question: 'Asked a question',
};

const KIND_TONE = {
  price: 'var(--error)',
  buy: 'var(--error)',
  availability: 'var(--primary-color)',
  contact: 'var(--primary-color)',
  interest: 'var(--secondary-color)',
  question: 'var(--text-muted)',
};

export default function LeadsPanel({ token, activeWorkspaceId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!activeWorkspaceId) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/leads`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      const body = await res.json().catch(() => ({}));
      setData(res.ok ? body : {
        leads: [], total: 0, unanswered: 0, commentsScanned: 0,
        summary: apiError(body, 'Could not read your comments just now.'),
      });
    } catch {
      setData({
        leads: [], total: 0, unanswered: 0, commentsScanned: 0,
        summary: 'Could not reach the server.',
      });
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId, token]);

  useEffect(() => { load(); }, [load]);

  const leads = data?.leads || [];
  const waiting = leads.filter((l) => !l.answered);
  const handled = leads.filter((l) => l.answered);

  return (
    <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <Inbox size={19} color="var(--primary-color)" />
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Leads in your comments</h2>
        {waiting.length > 0 && (
          <span style={{
            fontSize: '0.72rem', fontWeight: 800, padding: '0.15rem 0.55rem',
            borderRadius: 999, background: 'var(--error)', color: '#fff',
          }}>
            {waiting.length} waiting
          </span>
        )}
        <button
          onClick={load}
          disabled={loading}
          className="btn btn-secondary"
          style={{ marginLeft: 'auto', minHeight: 38, fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <RefreshCw size={14} className={loading ? 'spin' : undefined} /> Rescan
        </button>
      </div>

      <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', margin: '0 0 1.1rem', lineHeight: 1.55 }}>
        {loading ? 'Reading your comments…' : (data?.summary || '')}
      </p>

      {!loading && waiting.map((l, i) => (
        <a
          key={`w${i}`}
          href={l.postPermalink || '#'}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'block', textDecoration: 'none', color: 'inherit',
            padding: '0.9rem 1rem', marginBottom: '0.6rem', borderRadius: 10,
            background: 'rgba(11,16,32,0.03)',
            border: '1px solid ' + (KIND_TONE[l.kind] || 'var(--border-color)'),
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.35rem' }}>
            <strong style={{ fontSize: '0.86rem' }}>@{l.who || 'someone'}</strong>
            <span style={{ fontSize: '0.72rem', fontWeight: 800, color: KIND_TONE[l.kind] || 'var(--text-muted)' }}>
              {KIND_LABEL[l.kind] || l.why}
            </span>
            <ExternalLink size={12} style={{ marginLeft: 'auto', color: 'var(--text-muted)' }} />
          </div>
          <div style={{ fontSize: '0.9rem', lineHeight: 1.5, color: 'var(--text-main)' }}>
            “{l.text}”
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
            {/* The phrase that flagged it, so a false positive is obvious. */}
            matched “{l.matched}” · on “{l.postCaption || 'your post'}”
          </div>
        </a>
      ))}

      {!loading && handled.length > 0 && (
        <details style={{ marginTop: '0.5rem' }}>
          <summary style={{ cursor: 'pointer', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            {handled.length} already answered
          </summary>
          <div style={{ marginTop: '0.6rem' }}>
            {handled.map((l, i) => (
              <div key={`h${i}`} style={{
                display: 'flex', gap: '0.5rem', alignItems: 'flex-start',
                padding: '0.5rem 0', fontSize: '0.82rem', color: 'var(--text-muted)',
              }}>
                <CheckCircle2 size={14} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 2 }} />
                <span>@{l.who}: “{l.text}”</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
