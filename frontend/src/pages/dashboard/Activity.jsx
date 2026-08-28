import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollText, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Clock,
} from 'lucide-react';
import { API_BASE, authFetch } from '../../config';

/**
 * What the system has actually been doing, in one list.
 *
 * WHY
 * ---
 * This product runs on its own every few hours. Until now the only evidence
 * of that was posts appearing on accounts — and when something went wrong,
 * nothing surfaced it. One workspace had Facebook rejecting every post for a
 * fortnight while the dashboard showed green, because the failure was
 * recorded in a column nothing displayed.
 *
 * A customer paying monthly for automation needs to be able to answer "is it
 * working?" without being asked to trust a badge. This is that answer:
 * every publish and every run, in order, with the reason when one fails.
 *
 * Two sources, one timeline. `/marketing/logs` is what the loop did;
 * `/social/recent-posts` is what reached the platforms. Neither alone tells
 * the story — a loop that ran and published nothing looks identical to a
 * healthy one if you only read the first.
 */

const PLATFORM_LABEL = {
  ALL: 'every connected account',
  BOTH: 'Facebook and Instagram',
  FACEBOOK: 'Facebook',
  INSTAGRAM: 'Instagram',
  TWITTER: 'X',
  X: 'X',
  LINKEDIN: 'LinkedIn',
  YOUTUBE: 'YouTube',
};

const TONE = {
  ok: { color: 'var(--success)', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.22)', Icon: CheckCircle2 },
  partial: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)', Icon: AlertTriangle },
  bad: { color: '#f87171', bg: 'rgba(239,68,68,0.07)', border: 'rgba(239,68,68,0.22)', Icon: XCircle },
  idle: { color: 'var(--text-muted)', bg: 'rgba(11,16,32,0.03)', border: 'var(--border-color)', Icon: Clock },
};

function postToEntry(p) {
  const published = !!(p.fbPostId || p.igPostId || p.twitterPostId || p.linkedinPostId);
  const failed = p.status === 'FAILED';
  const scheduled = ['SCHEDULED', 'PENDING', 'DRAFT'].includes(p.status);

  // A post can publish on one platform and be refused by another. That is
  // neither a success nor a failure and must not be shown as either.
  let tone = 'idle';
  if (failed) tone = 'bad';
  else if (published && p.errorLog) tone = 'partial';
  else if (published || p.status === 'POSTED') tone = 'ok';

  const where = PLATFORM_LABEL[p.platform] || p.platform || 'your accounts';
  let title;
  if (scheduled) title = `Queued for ${where}`;
  else if (tone === 'bad') title = `Could not publish to ${where}`;
  else if (tone === 'partial') title = `Published, but not everywhere`;
  else title = `Published to ${where}`;

  return {
    key: `post-${p.id}`,
    at: p.postedAt || p.scheduledAt,
    tone,
    title,
    body: p.caption || '',
    detail: p.errorLog || '',
  };
}

function runToEntry(l) {
  const anything = l.socialSuccess || l.emailSuccess;
  const tone = l.errorLog ? (anything ? 'partial' : 'bad') : (anything ? 'ok' : 'idle');

  const did = [];
  if (l.socialSuccess) did.push('posted to social');
  if (l.emailSuccess) did.push(`sent ${l.emailCount || 0} email${l.emailCount === 1 ? '' : 's'}`);

  return {
    key: `run-${l.id}`,
    at: l.createdAt,
    tone,
    title: did.length ? `Automatic run — ${did.join(', ')}` : 'Automatic run — nothing to send',
    body: '',
    detail: l.errorLog || '',
  };
}

export default function Activity({ token, activeWorkspaceId }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('all');

  const load = useCallback(async () => {
    setRefreshing(true);
    const get = async (path) => {
      try {
        const res = await authFetch(`${API_BASE}${path}`, {
          headers: activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {},
        }, token);
        return res.ok ? await res.json() : null;
      } catch { return null; }
    };

    const [posts, runs] = await Promise.all([
      get('/social/recent-posts'),
      get('/marketing/logs'),
    ]);

    const list = [
      ...((posts?.data || posts || []).map ? (posts?.data || []).map(postToEntry) : []),
      ...(Array.isArray(runs) ? runs.map(runToEntry) : []),
    ].filter((e) => e.at);

    // Newest first. Two sources with independent clocks, so they are merged
    // by timestamp rather than concatenated.
    list.sort((a, b) => new Date(b.at) - new Date(a.at));

    setEntries(list);
    setLoading(false);
    setRefreshing(false);
  }, [token, activeWorkspaceId]);

  useEffect(() => { load(); }, [load]);

  const shown = filter === 'all'
    ? entries
    : entries.filter((e) => (filter === 'problems' ? e.tone === 'bad' || e.tone === 'partial' : e.tone === 'ok'));

  const problems = entries.filter((e) => e.tone === 'bad' || e.tone === 'partial').length;

  return (
    <div style={{ padding: '1.5rem', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
        <ScrollText size={20} color="var(--primary-color)" />
        <h1 style={{ margin: 0, fontSize: '1.3rem' }}>Activity log</h1>
        <button
          onClick={load}
          disabled={refreshing}
          className="btn btn-secondary"
          style={{ marginLeft: 'auto', minHeight: 38, fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <RefreshCw size={14} style={refreshing ? { animation: 'spin 1s linear infinite' } : undefined} />
          Refresh
        </button>
      </div>

      <p style={{ margin: '0 0 1.25rem', color: 'var(--text-muted)', fontSize: '0.88rem', lineHeight: 1.55 }}>
        Everything this account has done, newest first — each automatic run and
        every post that went out, with the reason when one did not.
      </p>

      <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '1.1rem', flexWrap: 'wrap' }}>
        {[
          ['all', `Everything (${entries.length})`],
          ['problems', `Needs attention (${problems})`],
          ['ok', 'Published'],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setFilter(id)}
            style={{
              minHeight: 34, padding: '0 0.75rem', borderRadius: 8, cursor: 'pointer',
              fontSize: '0.78rem', fontWeight: 700,
              background: filter === id ? 'var(--primary-color)' : 'transparent',
              color: filter === id ? '#fff' : 'var(--text-muted)',
              border: `1px solid ${filter === id ? 'var(--primary-color)' : 'var(--border-color)'}`,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && <p style={{ color: 'var(--text-muted)' }}>Loading…</p>}

      {!loading && shown.length === 0 && (
        <div style={{
          border: '1px dashed var(--border-color)', borderRadius: 12,
          padding: '2rem', textAlign: 'center', color: 'var(--text-muted)',
        }}>
          {entries.length === 0
            ? 'Nothing yet. Once an account is connected and the first post goes out, it will appear here.'
            : 'Nothing in this filter.'}
        </div>
      )}

      <div style={{ display: 'grid', gap: '0.6rem' }}>
        {shown.map((e) => {
          const tone = TONE[e.tone];
          const { Icon } = tone;
          return (
            <div key={e.key} style={{
              border: `1px solid ${tone.border}`, background: tone.bg,
              borderRadius: 10, padding: '0.85rem 1rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <Icon size={15} color={tone.color} />
                <strong style={{ fontSize: '0.86rem' }}>{e.title}</strong>
                <span style={{ marginLeft: 'auto', fontSize: '0.73rem', color: 'var(--text-muted)' }}>
                  {new Date(e.at).toLocaleString()}
                </span>
              </div>

              {e.body && (
                <div style={{
                  marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--text-muted)',
                  lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}>
                  {e.body}
                </div>
              )}

              {e.detail && (
                <div style={{
                  marginTop: '0.5rem', fontSize: '0.77rem', color: tone.color,
                  lineHeight: 1.45, fontWeight: 500,
                }}>
                  {e.detail}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
