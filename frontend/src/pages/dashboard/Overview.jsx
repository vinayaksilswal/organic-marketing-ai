import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2, Facebook, Instagram, Twitter, Linkedin, Activity,
  BarChart3, Clock, RefreshCw, Image as ImageIcon, AlertTriangle,
  Building2, Sparkles, XCircle, LogOut, Send, ArrowRight
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

  const panel = { background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, padding: '1.5rem', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' };
  const muted = { color: 'var(--text-muted)' };
  const [postFilter, setPostFilter] = useState('ALL'); // 'ALL' | 'POSTED' | 'SCHEDULED' | 'FAILED'

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
    !canPublish && { text: 'No social account connected', where: 'Businesses → Edit → Social Accounts', action: () => navigate('/dashboard/workspaces') },
    !hasMedia && { text: 'No media in this business’s catalog', where: 'Media & Catalog', action: () => navigate('/dashboard/media-catalog') },
    business && !business.brandAnalysisComplete && { text: 'Brand profile still building — captions will be generic', where: 'AI Video Studio', action: () => navigate('/dashboard/video-studio') },
  ].filter(Boolean);

  const Stat = ({ icon, label, value, hint, color = 'var(--primary-color)' }) => (
    <div style={{
      ...panel,
      display: 'flex',
      alignItems: 'center',
      gap: '1.15rem',
      position: 'relative',
      overflow: 'hidden',
      transition: 'transform 0.2s, box-shadow 0.2s',
    }}>
      <div style={{
        background: `linear-gradient(135deg, ${color}20, ${color}08)`,
        border: `1px solid ${color}30`,
        padding: '0.85rem',
        borderRadius: 12,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.83rem', fontWeight: 600, ...muted }}>{label}</div>
        {loading
          ? <div style={{ width: 52, height: 28, borderRadius: 6, background: 'rgba(11, 16, 32, 0.06)', marginTop: 4 }} />
          : <div style={{ fontSize: '1.75rem', fontWeight: 800, lineHeight: 1.2, color: 'var(--text-main)' }}>{value ?? 0}</div>}
        {hint && <div style={{ fontSize: '0.74rem', ...muted, marginTop: '0.15rem' }}>{hint}</div>}
      </div>
    </div>
  );

  const statusColor = live ? '#10b981' : '#f59e0b';

  const filteredPosts = recentPosts.filter(p => {
    if (postFilter === 'ALL') return true;
    if (postFilter === 'POSTED') return p.status === 'POSTED' || p.status === 'PUBLISHED';
    if (postFilter === 'FAILED') return p.status === 'FAILED';
    if (postFilter === 'SCHEDULED') return p.status === 'SCHEDULED' || p.status === 'DRAFT' || p.status === 'PENDING';
    return true;
  });

  return (
    <div className="view">
      <div className="container" style={{ padding: '2rem 0 3rem', maxWidth: 1100 }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.75rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2.1rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Command Center</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ ...muted, fontSize: '0.92rem', fontWeight: 550 }}>{business?.name || 'No business selected'}</span>
              <span style={{ color: 'var(--text-muted)' }}>•</span>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.2rem 0.65rem',
                borderRadius: 999,
                background: `${statusColor}18`,
                border: `1px solid ${statusColor}40`,
                color: statusColor,
                fontSize: '0.76rem',
                fontWeight: 750,
                letterSpacing: '0.02em',
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor }} />
                {live ? 'AUTONOMOUS POSTING ACTIVE' : 'NEEDS SETUP'}
              </span>
            </div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
            <button onClick={load} disabled={refreshing} className="btn btn-secondary"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', padding: '0.5rem 0.95rem', fontSize: '0.85rem', fontWeight: 600 }}>
              <RefreshCw size={14} style={refreshing ? { animation: 'spin 1s linear infinite' } : undefined} /> Refresh
            </button>
            <button
              onClick={handleLogout}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem',
                padding: '0.5rem 0.95rem', fontSize: '0.85rem', fontWeight: 600,
                cursor: 'pointer', borderRadius: 10,
                color: '#f87171',
                background: 'rgba(239,68,68,0.08)',
                border: '1px solid rgba(239,68,68,0.25)',
                transition: 'background .18s, border-color .18s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.16)';
                e.currentTarget.style.borderColor = 'rgba(239,68,68,0.5)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239,68,68,0.08)';
                e.currentTarget.style.borderColor = 'rgba(239,68,68,0.25)';
              }}
            >
              <LogOut size={14} /> Sign out
            </button>
          </div>
        </div>

        {/* Blockers / Setup Checklist */}
        {!loading && blockers.length > 0 && (
          <div style={{ ...panel, borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.04)', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <AlertTriangle size={16} color="#f59e0b" />
              <strong style={{ fontSize: '0.95rem', color: '#fcd34d' }}>
                {canPublish && hasMedia ? 'Action Items' : 'Automation Checklist — Action Required'}
              </strong>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {blockers.map((b, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.87rem', color: 'var(--text-main)', padding: '0.4rem 0' }}>
                  <span>• {b.text}</span>
                  {b.action && (
                    <button
                      onClick={b.action}
                      style={{
                        background: 'none', border: 'none', color: 'var(--primary-color)',
                        fontWeight: 650, cursor: 'pointer', fontSize: '0.82rem', textDecoration: 'underline'
                      }}
                    >
                      {b.where} →
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Core Metric Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          <Stat icon={<Activity size={20} color="var(--primary-color)" />} label="Posts Published" value={stats?.posts} color="var(--primary-color)" />
          <Stat icon={<BarChart3 size={20} color="#6366f1" />} label="Campaigns" value={stats?.campaigns} color="#6366f1" />
          <Stat icon={<ImageIcon size={20} color="#10b981" />} label="Media Library Assets" value={mediaCount} color="#10b981" />
          <Stat icon={<Building2 size={20} color="#f59e0b" />} label="Active Workspaces" value={stats?.workspaces} color="#f59e0b" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) 2fr', gap: '1.5rem', alignItems: 'start' }}>

          {/* Left Column: Channels & Automation Engine */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={panel}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700 }}>Connected Channels</h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Meta Graph API</span>
              </div>
              {connected.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  {connected.map((c, i) => (
                    <div key={i} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.65rem',
                      fontSize: '0.87rem',
                      padding: '0.5rem 0.65rem',
                      borderRadius: 8,
                      background: 'rgba(11, 16, 32, 0.03)',
                      border: '1px solid rgba(11, 16, 32, 0.05)',
                    }}>
                      <CheckCircle2 size={15} color="#10b981" />
                      {c.icon}
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 550 }}>{c.label}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem', color: 'var(--text-muted)', padding: '0.5rem 0' }}>
                  <XCircle size={15} color="#f87171" /> No accounts connected yet
                </div>
              )}
              <div style={{ marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid rgba(11, 16, 32, 0.06)', fontSize: '0.8rem', ...muted, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Manage connections:</span>
                <button onClick={() => navigate('/dashboard/workspaces')}
                  style={{ background: 'none', border: 'none', padding: 0, color: 'var(--primary-color)', cursor: 'pointer', fontWeight: 650, font: 'inherit' }}>
                  Businesses →
                </button>
              </div>
            </div>

            <div style={panel}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 700 }}>Autonomous Engine</h3>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  padding: '0.15rem 0.45rem',
                  borderRadius: 4,
                  background: schedulerStatus?.schedulerRunning ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                  color: schedulerStatus?.schedulerRunning ? 'var(--success)' : 'var(--error)',
                }}>
                  {schedulerStatus?.schedulerRunning ? 'ACTIVE' : 'STOPPED'}
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.86rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={muted}>Engine Status</span>
                  <span style={{ color: schedulerStatus?.schedulerRunning ? '#10b981' : '#f87171', fontWeight: 650 }}>
                    {schedulerStatus?.schedulerRunning ? 'Continuous Running' : 'Paused'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={muted}>Approval Mode</span>
                  <span style={{ color: schedulerStatus?.autoApprove ? '#10b981' : '#f59e0b', fontWeight: 650 }}>
                    {schedulerStatus?.autoApprove ? 'Auto-Publish' : 'Review Required'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={muted}>Publishing Cadence</span>
                  <span style={{ fontWeight: 650 }}>Every {business?.postIntervalHours ?? 2} Hours</span>
                </div>
                {schedulerStatus?.nextRunAt && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={muted}>Next Autonomous Post</span>
                    <span style={{ fontWeight: 650, color: 'var(--primary-color)' }}>{new Date(schedulerStatus.nextRunAt).toLocaleTimeString()}</span>
                  </div>
                )}
              </div>
              <div style={{ marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid rgba(11, 16, 32, 0.06)', textAlign: 'right' }}>
                <button
                  onClick={() => navigate('/dashboard/social-scheduler')}
                  style={{ background: 'none', border: 'none', color: 'var(--primary-color)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 650 }}
                >
                  Adjust Cadence &amp; Settings →
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Delivery Log & Post Review Queue */}
          <div style={{ ...panel, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(11, 16, 32, 0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Clock size={17} color="var(--primary-color)" />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>Post Delivery Log &amp; Reviews</h3>
              </div>

              {/* Filter Pills */}
              <div style={{ display: 'flex', gap: '0.35rem', background: 'rgba(11,16,32,0.04)', padding: '0.2rem', borderRadius: 8 }}>
                {['ALL', 'POSTED', 'SCHEDULED', 'FAILED'].map(f => (
                  <button
                    key={f}
                    onClick={() => setPostFilter(f)}
                    style={{
                      border: 'none',
                      background: postFilter === f ? 'var(--primary-color)' : 'transparent',
                      color: postFilter === f ? '#fff' : 'var(--text-muted)',
                      padding: '0.25rem 0.6rem',
                      borderRadius: 6,
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'background 0.15s, color 0.15s',
                    }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div style={{ padding: '3rem', textAlign: 'center' }}><span className="spinner" style={{ width: 22, height: 22 }} /></div>
            ) : filteredPosts.length === 0 ? (
              <div style={{ padding: '3.5rem 2rem', textAlign: 'center', fontSize: '0.9rem', ...muted }}>
                <Sparkles size={24} style={{ marginBottom: '0.75rem', opacity: 0.6, color: 'var(--primary-color)' }} />
                <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>No posts match this filter</div>
                <div style={{ fontSize: '0.82rem', marginTop: '0.35rem' }}>
                  Posts will appear here as the autonomous marketing loop publishes and schedules content.
                </div>
              </div>
            ) : (
              <div>
                {filteredPosts.slice(0, 8).map((p, i) => {
                  const ok = p.status === 'POSTED' || p.status === 'PUBLISHED';
                  const failed = p.status === 'FAILED';
                  const scheduled = p.status === 'SCHEDULED' || p.status === 'PENDING' || p.status === 'DRAFT';
                  const color = ok ? '#10b981' : failed ? '#f87171' : '#f59e0b';
                  return (
                    <div key={p.id || i} style={{
                      display: 'flex',
                      gap: '0.95rem',
                      padding: '1rem 1.5rem',
                      borderBottom: '1px solid rgba(11, 16, 32, 0.04)',
                      transition: 'background 0.15s',
                    }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, marginTop: 6, flexShrink: 0 }} />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: '0.88rem', fontWeight: 500, lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', color: 'var(--text-main)' }}>
                          {p.caption || 'AI Generated Creative Asset'}
                        </div>
                        <div style={{ display: 'flex', gap: '0.65rem', marginTop: '0.35rem', fontSize: '0.75rem', ...muted, flexWrap: 'wrap', alignItems: 'center' }}>
                          <span style={{
                            color,
                            fontWeight: 750,
                            padding: '0.1rem 0.45rem',
                            borderRadius: 4,
                            background: `${color}15`,
                            fontSize: '0.7rem',
                            letterSpacing: '0.04em',
                          }}>
                            {p.status}
                          </span>
                          <span style={{ fontWeight: 600 }}>{p.platform || 'INSTAGRAM / FACEBOOK'}</span>
                          {p.scheduledAt && <span>{new Date(p.scheduledAt).toLocaleString()}</span>}
                        </div>
                        {failed && p.errorLog && (
                          <div style={{
                            fontSize: '0.76rem',
                            color: '#fca5a5',
                            marginTop: '0.4rem',
                            padding: '0.4rem 0.65rem',
                            borderRadius: 6,
                            background: 'rgba(239,68,68,0.06)',
                            border: '1px solid rgba(239,68,68,0.2)',
                            lineHeight: 1.4,
                          }}>
                            {p.errorLog}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
                <div style={{ padding: '1rem 1.5rem', textAlign: 'center', background: 'rgba(11, 16, 32, 0.015)' }}>
                  <button onClick={() => navigate('/dashboard/social-scheduler')}
                    style={{ background: 'none', border: 'none', color: 'var(--primary-color)', cursor: 'pointer', fontSize: '0.86rem', fontWeight: 700 }}>
                    Open Social Scheduler &amp; Review Calendar →
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
