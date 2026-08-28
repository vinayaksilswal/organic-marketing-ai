import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Clock, RefreshCw } from 'lucide-react';
import { API_BASE, authFetch } from '../config';

/**
 * Is each connected account actually publishing?
 *
 * WHY THIS IS ITS OWN PANEL
 * -------------------------
 * Two Pages rejected every Facebook post for a fortnight. The reason was
 * recorded — on individual posts, behind a green POSTED badge, on posts that
 * were also succeeding on Instagram. A per-post error is the wrong altitude
 * for a standing problem: "this post failed" is noise you scroll past, while
 * "Facebook has published nothing since 11 August" is a thing somebody fixes.
 *
 * Only shown when there is something to say. A row of green ticks on a
 * healthy account is furniture, and furniture at the top of a dashboard is
 * what trains people to stop reading it.
 */

const STATE = {
  action_required: {
    Icon: XCircle, colour: '#f87171',
    bg: 'rgba(239,68,68,0.07)', border: 'rgba(239,68,68,0.28)',
  },
  degraded: {
    Icon: AlertTriangle, colour: '#f59e0b',
    bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.28)',
  },
  unknown: {
    Icon: Clock, colour: 'var(--text-muted)',
    bg: 'rgba(11,16,32,0.03)', border: 'var(--border-color)',
  },
  healthy: {
    Icon: CheckCircle2, colour: 'var(--success)',
    bg: 'rgba(16,185,129,0.07)', border: 'rgba(16,185,129,0.22)',
  },
};

const daysAgo = (iso) => {
  if (!iso) return null;
  const days = Math.floor((Date.now() - new Date(iso)) / 86400000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
};

export default function PublishingHealth({ token, activeWorkspaceId, alwaysShow = false }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!activeWorkspaceId) return;
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/social/publishing-health`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      const body = await res.json().catch(() => ({}));
      if (res.ok && body?.success) setRows(body.data || []);
    } catch {
      /* The dashboard is still usable without this. */
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId, token]);

  useEffect(() => { load(); }, [load]);

  const problems = rows.filter((r) => r.state === 'action_required' || r.state === 'degraded');
  const shown = alwaysShow ? rows : problems;

  if (shown.length === 0) return null;

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border-color)',
      borderRadius: 14, padding: '1.35rem', marginBottom: '1.5rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', marginBottom: '0.9rem', flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: '1rem' }}>Publishing health</h2>
        {problems.length > 0 && (
          <span style={{
            fontSize: '0.7rem', fontWeight: 800, padding: '0.12rem 0.5rem',
            borderRadius: 999, background: 'rgba(239,68,68,0.12)', color: '#f87171',
          }}>
            {problems.length} need{problems.length === 1 ? 's' : ''} attention
          </span>
        )}
        <button
          onClick={load}
          disabled={loading}
          className="btn btn-secondary"
          style={{ marginLeft: 'auto', minHeight: 32, fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
        >
          <RefreshCw size={12} style={loading ? { animation: 'spin 1s linear infinite' } : undefined} />
          Recheck
        </button>
      </div>

      <div style={{ display: 'grid', gap: '0.55rem' }}>
        {shown.map((r) => {
          const tone = STATE[r.state] || STATE.unknown;
          const { Icon } = tone;
          return (
            <div key={r.platform} style={{
              border: `1px solid ${tone.border}`, background: tone.bg,
              borderRadius: 10, padding: '0.8rem 0.95rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <Icon size={15} color={tone.colour} />
                <strong style={{ fontSize: '0.88rem' }}>{r.label}</strong>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{r.headline}</span>
                {/* "Last published 17 days ago" is the line that turns a vague
                    worry into a date somebody can reason about. */}
                {r.lastSuccess && (
                  <span style={{ marginLeft: 'auto', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    last published {daysAgo(r.lastSuccess)}
                  </span>
                )}
              </div>

              {r.reason && (
                <div style={{
                  marginTop: '0.5rem', fontSize: '0.79rem', lineHeight: 1.5,
                  color: 'var(--text-muted)',
                }}>
                  {r.reason}
                </div>
              )}

              {/* What to do, when we have actually seen this error before.
                  Guessing at guidance for an unknown failure would put
                  confident wrong advice in front of somebody mid-problem. */}
              {r.guidance && (
                <div style={{
                  marginTop: '0.55rem', fontSize: '0.8rem', lineHeight: 1.55,
                  fontWeight: 600, color: tone.colour,
                }}>
                  {r.guidance}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
