import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3, Instagram, Facebook, RefreshCw, ExternalLink,
  AlertTriangle, Users, Heart, MessageCircle,
} from 'lucide-react';
import { API_BASE, authFetch } from '../../config';

/**
 * What the connected accounts are actually doing.
 *
 * Every number here is read live from the account itself, so a field the
 * platform did not return is shown as "not reported" rather than as zero.
 * Those look identical on a dashboard and mean opposite things: one is a post
 * nobody engaged with, the other is a permission we do not have.
 */

const nf = (n) => (typeof n === 'number' ? n.toLocaleString() : '—');

const PLATFORM = {
  instagram: { Icon: Instagram, colour: '#E4405F', label: 'Instagram' },
  facebook: { Icon: Facebook, colour: '#1877F2', label: 'Facebook Page' },
};

const Stat = ({ label, value, hint }) => (
  <div style={{ flex: '1 1 120px', minWidth: 0 }}>
    <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.15 }}>
      {value}
    </div>
    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600 }}>{label}</div>
    {hint && <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 2 }}>{hint}</div>}
  </div>
);

const AccountCard = ({ account }) => {
  const meta = PLATFORM[account.platform] || PLATFORM.instagram;
  const { Icon, colour, label } = meta;
  const s = account.summary || {};
  const posts = account.posts || [];

  return (
    <div className="glass-panel" style={{ padding: '1.4rem', marginBottom: '1.25rem' }}>
      {/* Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '1.1rem', flexWrap: 'wrap' }}>
        {account.avatar
          ? <img src={account.avatar} alt="" width={44} height={44}
                 style={{ borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }} />
          : <div style={{
              width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
              background: `${colour}18`, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}><Icon size={20} color={colour} /></div>}
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 800, fontSize: '1.02rem' }}>{account.name || label}</span>
            <Icon size={14} color={colour} />
          </div>
          {account.handle && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>@{account.handle}</div>
          )}
        </div>
        {account.link && (
          <a href={account.link} target="_blank" rel="noreferrer"
             style={{ fontSize: '0.78rem', color: 'var(--primary-color)', display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
            Open <ExternalLink size={12} />
          </a>
        )}
      </div>

      {account.unavailable ? (
        <div style={{
          display: 'flex', gap: '0.55rem', alignItems: 'flex-start',
          padding: '0.75rem 0.85rem', borderRadius: 10,
          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
          fontSize: '0.85rem', lineHeight: 1.5,
        }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2, color: 'var(--error)' }} />
          <span>{account.unavailable}</span>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: s.available ? '1.25rem' : 0 }}>
            <Stat label="Followers" value={nf(account.followers)} />
            {typeof account.totalPosts === 'number' && <Stat label="Posts" value={nf(account.totalPosts)} />}
            {s.available && <Stat label={`Posts · ${s.windowDays}d`} value={nf(s.postsInWindow)} />}
            {s.available && <Stat label="Median engagement" value={nf(s.medianEngagement)} hint="likes + comments" />}
            {s.available && <Stat label="Best post" value={nf(s.bestEngagement)} />}
          </div>

          {!s.available && (
            <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
              {s.note || 'No engagement figures were returned for this account.'}
            </p>
          )}

          {s.available && s.byFormat && Object.keys(s.byFormat).length > 1 && (
            <div style={{ marginBottom: '1.1rem' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-muted)', marginBottom: '0.45rem' }}>
                By format
              </div>
              <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
                {Object.entries(s.byFormat).map(([kind, v]) => (
                  <span key={kind} style={{
                    fontSize: '0.76rem', padding: '0.3rem 0.6rem', borderRadius: 8,
                    background: 'rgba(11,16,32,0.04)', border: '1px solid var(--border-color)',
                  }}>
                    <strong>{kind}</strong> · {v.median} median · {v.posts} posts
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Recent posts */}
          {posts.length > 0 && (
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.05em', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Last {posts.length} posts
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: 340, overflowY: 'auto' }}>
                {posts.map((p) => (
                  <a key={p.id} href={p.permalink || '#'} target="_blank" rel="noreferrer"
                     style={{
                       display: 'flex', alignItems: 'center', gap: '0.6rem',
                       padding: '0.45rem', borderRadius: 10, textDecoration: 'none',
                       border: '1px solid var(--border-color)', color: 'inherit',
                     }}>
                    {p.thumbnail
                      ? <img src={p.thumbnail} alt="" width={38} height={38} loading="lazy"
                             style={{ borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />
                      : <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgba(11,16,32,0.05)', flexShrink: 0 }} />}
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <span style={{ display: 'block', fontSize: '0.79rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {p.caption || <em style={{ color: 'var(--text-muted)' }}>No caption</em>}
                      </span>
                      <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {p.kind} · {new Date(p.postedAt).toLocaleDateString()}
                      </span>
                    </span>
                    <span style={{ display: 'flex', gap: '0.6rem', fontSize: '0.75rem', color: 'var(--text-muted)', flexShrink: 0 }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                        <Heart size={12} /> {p.likes ?? '—'}
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                        <MessageCircle size={12} /> {p.comments ?? '—'}
                      </span>
                    </span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

const AccountInsights = ({ token, activeWorkspaceId }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!activeWorkspaceId) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/account-insights`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      setData(res.ok ? await res.json() : { accounts: [], note: `Could not load insights (error ${res.status}).` });
    } catch (e) {
      setData({ accounts: [], note: 'Could not reach the server.' });
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId, token]);

  useEffect(() => { load(); }, [load]);

  const accounts = data?.accounts || [];

  return (
    <div className="container" style={{ padding: '2.5rem 0', }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
        <BarChart3 size={25} color="var(--primary-color)" />
        <h1 style={{ margin: 0 }}>Account Insights</h1>
        <button onClick={load} disabled={loading} className="btn btn-secondary"
                style={{ marginLeft: 'auto', minHeight: 40, display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>
      <p style={{ color: 'var(--text-muted)', marginBottom: '1.75rem' }}>
        Read live from each account connected to this business — not from what we published.
      </p>

      {loading ? (
        <p style={{ color: 'var(--text-muted)' }}>Reading your accounts…</p>
      ) : accounts.length === 0 ? (
        <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }}>
          <Users size={26} color="var(--text-muted)" style={{ marginBottom: '0.75rem' }} />
          <p style={{ margin: 0, color: 'var(--text-muted)' }}>
            {data?.note || 'No social account is connected to this business yet.'}
          </p>
        </div>
      ) : accounts.map((a) => <AccountCard key={`${a.platform}-${a.id}`} account={a} />)}
    </div>
  );
};

export default AccountInsights;
