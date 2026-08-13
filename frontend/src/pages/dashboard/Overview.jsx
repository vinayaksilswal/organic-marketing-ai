import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2, Facebook, Instagram, Twitter, Linkedin, Activity,
  BarChart3, Clock, RefreshCw, Image as ImageIcon, AlertTriangle,
  Building2, Sparkles, XCircle, LogOut
} from 'lucide-react';
import { API_BASE, authFetch } from '../../config';

/**
 * Command Center — a read-only status view.
 *
 * Deliberately contains no actions. Connecting accounts, uploading media and
 * running automation each already have a canonical home; duplicating them here
 * made it ambiguous which control was authoritative. This page answers one
 * question: is my marketing running, and what has it done lately.
 */
const Dashboard = ({ user, token, showToast, activeWorkspaceId, onLogout }) => {
  const navigate = useNavigate();
  const [business, setBusiness] = useState(null);
  const [connection, setConnection] = useState(null);
  const [recentPosts, setRecentPosts] = useState([]);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [mediaCount, setMediaCount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Confirmed first. Logging out is not destructive, but an accidental one
  // costs the operator a re-login in the middle of whatever they were doing,
  // and this button sits directly under the one they press most.
  //
  // Falls back to clearing the session itself if the prop is missing, so the
  // button always works rather than silently doing nothing.
  const handleLogout = () => {
    if (!window.confirm('Log out of Organiflo?')) return;
    if (typeof onLogout === 'function') {
      onLogout();
      return;
    }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/';
  };

  const load = useCallback(async () => {
    setRefreshing(true);
    const get = async (path) => {
      try {
        const res = await authFetch(`${API_BASE}${path}`, {}, token);
        return res.ok ? await res.json() : null;
      } catch { return null; }
    };

    const [biz, posts, sched, st, media] = await Promise.all([
      get('/businesses'),
      get('/social/recent-posts'),
      get('/social/scheduler-status'),
      get('/stats'),
      get('/marketing/media'),
    ]);

    if (Array.isArray(biz)) {
      const active = biz.find(b => b.id === activeWorkspaceId) || biz[0] || null;
      setBusiness(active);
      setConnection(active?.socialConnection || null);
    }
    if (posts?.success && posts.data) setRecentPosts(posts.data);
    if (sched?.success && sched.data) setSchedulerStatus(sched.data);
    if (st?.success && st.data) setStats(st.data);
    if (Array.isArray(media)) setMediaCount(media.length);

    setLoading(false);
    setRefreshing(false);
  }, [token, activeWorkspaceId]);

  useEffect(() => { load(); }, [load]);

  const panel = { background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: '1.5rem' };
  const muted = { color: 'rgba(255,255,255,0.45)' };

  const connected = [
    connection?.hasFacebook && { icon: <Facebook size={14} color="#60a5fa" />, label: connection.fbPageName || 'Facebook Page' },
    connection?.igAccountId && { icon: <Instagram size={14} color="#f472b6" />, label: `@${connection.igAccountName || 'instagram'}` },
    connection?.hasLinkedin && { icon: <Linkedin size={14} color="#93c5fd" />, label: 'LinkedIn' },
    connection?.hasTwitter && { icon: <Twitter size={14} color="#e5e7eb" />, label: 'X (Twitter)' },
  ].filter(Boolean);

  // The engine is only genuinely running when it can both create and publish.
  const canPublish = connected.length > 0;
  const hasMedia = (mediaCount ?? 0) > 0;
  const live = canPublish && hasMedia;

  const blockers = [
    !canPublish && { text: 'No social account connected', where: 'Businesses → Edit → Social Accounts' },
    !hasMedia && { text: 'No media in this business’s catalog', where: 'Media & Catalog' },
    business && !business.brandAnalysisComplete && { text: 'Brand profile still building — captions will be generic', where: null },
  ].filter(Boolean);

  const Stat = ({ icon, label, value, hint }) => (
    <div style={{ ...panel, display: 'flex', alignItems: 'center', gap: '1.15rem' }}>
      <div style={{ background: 'rgba(139,92,246,0.1)', padding: '0.9rem', borderRadius: 12, display: 'flex' }}>{icon}</div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.85rem', ...muted }}>{label}</div>
        {loading
          ? <div style={{ width: 52, height: 30, borderRadius: 6, background: 'rgba(255,255,255,0.06)', marginTop: 4 }} />
          : <div style={{ fontSize: '1.85rem', fontWeight: 700, lineHeight: 1.2 }}>{value ?? 0}</div>}
        {hint && <div style={{ fontSize: '0.75rem', ...muted }}>{hint}</div>}
      </div>
    </div>
  );

  const statusColor = live ? '#10b981' : '#f59e0b';

  return (
    <div className="view">
      <div className="container" style={{ padding: '2.5rem 0 3rem' }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2.25rem' }}>Command Center</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
              <span style={{ ...muted, fontSize: '0.95rem' }}>{business?.name || 'No business selected'} —</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.2rem 0.65rem', borderRadius: 999, background: `${statusColor}22`, color: statusColor, fontSize: '0.78rem', fontWeight: 700 }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: statusColor }} />
                {live ? 'AUTOMATION LIVE' : 'NOT PUBLISHING'}
              </span>
            </div>
          </div>
          {/* Stacked, so the destructive action is never where the muscle
              memory for Refresh lands. */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: '0.55rem' }}>
            <button onClick={load} disabled={refreshing} className="btn btn-secondary"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', padding: '0.5rem 0.9rem', fontSize: '0.85rem' }}>
              <RefreshCw size={14} style={refreshing ? { animation: 'spin 1s linear infinite' } : undefined} /> Refresh
            </button>
            <button
              onClick={handleLogout}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                padding: '0.5rem 0.9rem', fontSize: '0.85rem', fontWeight: 600,
                cursor: 'pointer', borderRadius: 12,
                color: '#f87171',
                background: 'rgba(239,68,68,0.10)',
                border: '1px solid rgba(239,68,68,0.32)',
                transition: 'background .18s, border-color .18s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.18)';
                e.currentTarget.style.borderColor = 'rgba(239,68,68,0.55)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.10)';
                e.currentTarget.style.borderColor = 'rgba(239,68,68,0.32)';
              }}
            >
              <LogOut size={14} /> Log out
            </button>
          </div>
        </div>

        {/* Blockers — the reason it is not publishing, stated plainly */}
        {!loading && blockers.length > 0 && (
          <div style={{ ...panel, borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.05)', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <AlertTriangle size={16} color="#f59e0b" />
              <strong style={{ fontSize: '0.95rem', color: '#fcd34d' }}>
                {canPublish && hasMedia ? 'Worth attending to' : 'Automation cannot publish yet'}
              </strong>
            </div>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {blockers.map((b, i) => (
                <li key={i} style={{ fontSize: '0.87rem', color: 'rgba(255,255,255,0.75)' }}>
                  {b.text}{b.where && <span style={{ ...muted }}> — {b.where}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Counts */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
          <Stat icon={<Activity size={22} color="var(--primary-color)" />} label="Posts published" value={stats?.posts} />
          <Stat icon={<BarChart3 size={22} color="var(--secondary-color)" />} label="Campaigns" value={stats?.campaigns} />
          <Stat icon={<ImageIcon size={22} color="#10b981" />} label="Media assets" value={mediaCount} />
          <Stat icon={<Building2 size={22} color="#f59e0b" />} label="Businesses" value={stats?.workspaces} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 1fr) 2fr', gap: '1.5rem', alignItems: 'start' }}>

          {/* Status column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={panel}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Connected accounts</h3>
              {connected.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {connected.map((c, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', fontSize: '0.87rem' }}>
                      <CheckCircle2 size={14} color="#10b981" />
                      {c.icon}
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.label}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem', color: 'rgba(255,255,255,0.5)' }}>
                  <XCircle size={14} color="#f87171" /> None connected
                </div>
              )}
              <div style={{ marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid rgba(255,255,255,0.06)', fontSize: '0.78rem', ...muted }}>
                Managed in{' '}
                <button onClick={() => navigate('/dashboard/workspaces')}
                  style={{ background: 'none', border: 'none', padding: 0, color: 'var(--primary-color)', cursor: 'pointer', font: 'inherit' }}>
                  Businesses
                </button>
              </div>
            </div>

            <div style={panel}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Automation</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={muted}>Scheduler</span>
                  <span style={{ color: schedulerStatus?.schedulerRunning ? '#10b981' : '#f87171', fontWeight: 600 }}>
                    {schedulerStatus?.schedulerRunning ? 'Running' : 'Stopped'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={muted}>Auto-approve</span>
                  <span style={{ color: schedulerStatus?.autoApprove ? '#10b981' : '#f59e0b', fontWeight: 600 }}>
                    {schedulerStatus?.autoApprove ? 'On — publishes directly' : 'Off — queues drafts'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={muted}>Posts every</span>
                  <span style={{ fontWeight: 600 }}>{business?.postIntervalHours ?? 2}h</span>
                </div>
                {schedulerStatus?.nextRunAt && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={muted}>Next run</span>
                    <span style={{ fontWeight: 600 }}>{new Date(schedulerStatus.nextRunAt).toLocaleTimeString()}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Recent activity */}
          <div style={{ ...panel, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Clock size={16} color="var(--primary-color)" />
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Recent posts</h3>
              <span style={{ marginLeft: 'auto', fontSize: '0.78rem', ...muted }}>{recentPosts.length} shown</span>
            </div>

            {loading ? (
              <div style={{ padding: '3rem', textAlign: 'center' }}><span className="spinner" style={{ width: 20, height: 20 }} /></div>
            ) : recentPosts.length === 0 ? (
              <div style={{ padding: '3rem 2rem', textAlign: 'center', fontSize: '0.9rem', ...muted }}>
                <Sparkles size={22} style={{ marginBottom: '0.75rem', opacity: 0.5 }} />
                <div>Nothing published yet.</div>
                <div style={{ fontSize: '0.82rem', marginTop: '0.35rem' }}>
                  Posts appear here once the automation runs.
                </div>
              </div>
            ) : (
              <div>
                {recentPosts.slice(0, 8).map((p, i) => {
                  const ok = p.status === 'POSTED';
                  const failed = p.status === 'FAILED';
                  const color = ok ? '#10b981' : failed ? '#f87171' : '#f59e0b';
                  return (
                    <div key={p.id || i} style={{ display: 'flex', gap: '0.85rem', padding: '0.9rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, marginTop: 7, flexShrink: 0 }} />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: '0.86rem', lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                          {p.caption || 'No caption'}
                        </div>
                        <div style={{ display: 'flex', gap: '0.6rem', marginTop: '0.3rem', fontSize: '0.74rem', ...muted, flexWrap: 'wrap' }}>
                          <span style={{ color, fontWeight: 600 }}>{p.status}</span>
                          <span>{p.platform}</span>
                          {p.scheduledAt && <span>{new Date(p.scheduledAt).toLocaleString()}</span>}
                        </div>
                        {failed && p.errorLog && (
                          <div style={{ fontSize: '0.74rem', color: '#fca5a5', marginTop: '0.25rem' }}>{p.errorLog}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div style={{ padding: '0.85rem 1.5rem', textAlign: 'center' }}>
                  <button onClick={() => navigate('/dashboard/social-scheduler')}
                    style={{ background: 'none', border: 'none', color: 'var(--primary-color)', cursor: 'pointer', fontSize: '0.83rem', fontWeight: 600 }}>
                    View full delivery log
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
