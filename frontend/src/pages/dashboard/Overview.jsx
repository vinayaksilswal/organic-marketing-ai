import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, CheckCircle2, Facebook, Instagram, Twitter, Linkedin, Sparkles, BarChart3, Activity, Clock, RefreshCw, Send } from 'lucide-react';
import { API_BASE, authFetch } from '../../config';


const Dashboard = ({ user, token, showToast, activeWorkspaceId }) => {
  const navigate = useNavigate();
  // Real connection state for the active workspace, loaded from the API.
  const [connection, setConnection] = useState(null);
  const [activeBusiness, setActiveBusiness] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [files, setFiles] = useState([]);
  const [baseCaption, setBaseCaption] = useState('');
  const [loading, setLoading] = useState(false);
  const [recentPosts, setRecentPosts] = useState([]);
  const [schedulerStatus, setSchedulerStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboardData = async () => {
    setRefreshing(true);
    try {
      const postsRes = await authFetch(`${API_BASE}/social/recent-posts`, {}, token);
      if (postsRes.ok) {
        const postsData = await postsRes.json();
        if (postsData.success && postsData.data) {
          setRecentPosts(postsData.data);
        }
      }

      const schedRes = await authFetch(`${API_BASE}/social/scheduler-status`, {}, token);
      if (schedRes.ok) {
        const schedData = await schedRes.json();
        if (schedData.success && schedData.data) {
          setSchedulerStatus(schedData.data);
        }
      }

      const statsRes = await authFetch(`${API_BASE}/stats`, {}, token);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        if (statsData.success && statsData.data) {
          setStats(statsData.data);
        }
      }

      // Real social connection state for the active workspace
      const bizRes = await authFetch(`${API_BASE}/businesses`, {}, token);
      if (bizRes.ok) {
        const businesses = await bizRes.json();
        const active = Array.isArray(businesses)
          ? businesses.find(b => b.id === activeWorkspaceId) || businesses[0]
          : null;
        setConnection(active?.socialConnection || null);
        setActiveBusiness(active || null);
      }
    } catch (err) {
      // SystemBanner already reports backend outages persistently. Toasting on
      // every failed poll produced a stream of duplicate errors that buried any
      // message the user actually needed to act on.
      console.error('Error fetching dashboard data:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [token, activeWorkspaceId]);

  // Report the outcome of the Meta OAuth round-trip when redirected back here
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const meta = params.get('meta');
    if (!meta) return;
    const message = params.get('message');
    if (meta === 'connected') {
      showToast(`Connected ${message || 'your Meta account'}.`);
      fetchDashboardData();
    } else {
      showToast(message || 'Could not connect your Meta account.', true);
    }
    window.history.replaceState({}, '', window.location.pathname);
  }, []);

  const handleConnectMeta = async () => {
    if (!activeWorkspaceId) {
      return showToast('Select a business first, then connect its accounts.', true);
    }
    setConnecting(true);
    try {
      const res = await authFetch(
        `${API_BASE}/meta/connect?workspace_id=${encodeURIComponent(activeWorkspaceId)}`, {}, token
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.authUrl) {
        throw new Error(data.detail || data.message || 'Meta connection is unavailable right now.');
      }
      window.location.href = data.authUrl;
    } catch (err) {
      showToast(err.message, true);
      setConnecting(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const newFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files).filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const startAutomation = async () => {
    if (files.length === 0 && !baseCaption.trim()) {
      return showToast('Please provide a campaign angle or upload media.', true);
    }
    
    const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
    for (const f of files) {
      if (f.size > MAX_FILE_SIZE) {
        return showToast(`File ${f.name} exceeds the 50MB limit.`, true);
      }
    }

    setLoading(true);
    try {
      let uploadedMediaUrl = 'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=800';
      let mediaType = 'image';

      if (files.length > 0) {
        const fileToUpload = files[0];
        mediaType = fileToUpload.type.startsWith('video/') ? 'video' : 'image';
        const formData = new FormData();
        formData.append('file', fileToUpload);

        const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
        const uploadRes = await fetch(`${API_BASE}/upload-media`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${token}`,
            ...(activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {})
          },
          body: formData
        });

        if (uploadRes.ok) {
          const uploadData = await uploadRes.json();
          if (uploadData.success && uploadData.data?.url) {
            uploadedMediaUrl = uploadData.data.url;
          }
        }
      }

      // 1. Create Social Campaign record
      const campaignRes = await authFetch(`${API_BASE}/campaigns`, {
        method: 'POST',
        body: JSON.stringify({
          baseCaption: baseCaption || 'Automated high-converting growth post by OrganicAI',
          mediaUrl: uploadedMediaUrl,
          mediaType: mediaType
        })
      }, token);

      if (!campaignRes.ok) {
        const errJson = await campaignRes.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to create campaign record');
      }

      // 2. Trigger immediate social marketing loop iteration
      const triggerRes = await authFetch(`${API_BASE}/social/trigger`, {
        method: 'POST'
      }, token);

      if (!triggerRes.ok) {
        const errJson = await triggerRes.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to trigger marketing loop');
      }

      showToast('Campaign Generated! Marketing loop triggered successfully.');
      setFiles([]);
      setBaseCaption('');
      fetchDashboardData();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
          <div>
            <h1>Command Center</h1>
            <p className="text-muted" style={{ fontSize: '1.125rem' }}>
              Welcome back. Your automation engine is <span className="badge active"><span className="status-dot green"></span>Active</span>
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ margin: 0, fontWeight: '600' }}>Pro Plan <span style={{ color: 'var(--primary-color)' }}>$17/mo</span></p>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)' }}>{user?.email}</p>
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '3rem' }}>
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '1rem', borderRadius: '12px' }}>
              <Activity size={24} color="var(--primary-color)" />
            </div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--text-muted)', fontWeight: '500' }}>Posts Generated</h4>
              {refreshing && !stats ? <div className="skeleton-card" style={{ width: '60px', height: '36px', borderRadius: '6px' }}></div> : <h2 style={{ margin: 0 }}>{stats ? stats.posts : (recentPosts.length || 0)}</h2>}
            </div>
          </div>
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '1rem', borderRadius: '12px' }}>
              <BarChart3 size={24} color="var(--secondary-color)" />
            </div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--text-muted)', fontWeight: '500' }}>Total Campaigns</h4>
              {refreshing && !stats ? <div className="skeleton-card" style={{ width: '60px', height: '36px', borderRadius: '6px' }}></div> : <h2 style={{ margin: 0 }}>{stats ? stats.campaigns : 0}</h2>}
            </div>
          </div>
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '1rem', borderRadius: '12px' }}>
              <Sparkles size={24} color="var(--success)" />
            </div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--text-muted)', fontWeight: '500' }}>Active Users</h4>
              {refreshing && !stats ? <div className="skeleton-card" style={{ width: '60px', height: '36px', borderRadius: '6px' }}></div> : <h2 style={{ margin: 0 }}>{stats ? stats.users : 1}</h2>}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
          {/* Left Column: Integrations & Scheduler Status */}
          <div>
            <div className="glass-panel" style={{ padding: '2rem', marginBottom: '2rem' }}>
              <h3>Connected Platforms</h3>
              <p style={{ fontSize: '0.875rem', marginBottom: '2rem', color: 'var(--text-muted)' }}>Link your accounts to enable automated posting.</p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* Meta — real OAuth */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <Facebook size={19} color="#1877F2" />
                      <Instagram size={19} color="#E4405F" />
                      <span style={{ fontWeight: '600' }}>Meta</span>
                    </div>
                    {connection?.hasFacebook ? (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.7rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '999px', background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
                        <CheckCircle2 size={11} /> CONNECTED
                      </span>
                    ) : (
                      <button
                        onClick={handleConnectMeta}
                        disabled={connecting}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.4rem 0.8rem', fontSize: '0.8rem', fontWeight: 600, borderRadius: '7px', background: '#1877f2', color: '#fff', border: 'none', cursor: connecting ? 'wait' : 'pointer', opacity: connecting ? 0.7 : 1, whiteSpace: 'nowrap' }}
                      >
                        <Facebook size={13} /> {connecting ? 'Redirecting…' : 'Connect'}
                      </button>
                    )}
                  </div>
                  {connection?.hasFacebook && (
                    <div style={{ marginTop: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.82rem', color: 'rgba(255,255,255,0.75)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <Facebook size={13} color="#60a5fa" /> {connection.fbPageName || 'Facebook Page'}
                      </div>
                      {connection.igAccountId && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                          <Instagram size={13} color="#f472b6" /> @{connection.igAccountName || 'instagram'}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* X and LinkedIn — token-based, configured per business */}
                {[
                  { key: 'hasTwitter', label: 'X (Twitter)', icon: <Twitter size={19} color="#1DA1F2" /> },
                  { key: 'hasLinkedin', label: 'LinkedIn', icon: <Linkedin size={19} color="#0A66C2" /> },
                ].map(p => (
                  <div key={p.key} style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        {p.icon}
                        <span style={{ fontWeight: '600' }}>{p.label}</span>
                      </div>
                      {connection?.[p.key] ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.7rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '999px', background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
                          <CheckCircle2 size={11} /> CONNECTED
                        </span>
                      ) : (
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem', whiteSpace: 'nowrap' }}
                          onClick={() => navigate('/dashboard/workspaces')}
                        >
                          Set up
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                <p style={{ margin: 0, fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)', lineHeight: 1.5 }}>
                  Accounts are linked per business. Manage them under{' '}
                  <button onClick={() => navigate('/dashboard/workspaces')}
                    style={{ background: 'none', border: 'none', padding: 0, color: 'var(--primary-color)', cursor: 'pointer', font: 'inherit' }}>
                    Businesses → Social Accounts
                  </button>.
                </p>
              </div>
            </div>

            {/* Scheduler Details Panel */}
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Clock size={18} color="var(--primary-color)" /> Automation Loop
                </h4>
                <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={fetchDashboardData} disabled={refreshing}>
                  <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
                </button>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                Bi-hourly automated scheduling loop status:
              </p>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.75rem 1rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span>Status:</span>
                  <span style={{ fontWeight: '600', color: schedulerStatus?.schedulerRunning ? 'var(--success)' : 'var(--text-muted)' }}>
                    {schedulerStatus?.schedulerRunning ? 'RUNNING' : 'ACTIVE'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Auto Approve:</span>
                  <span style={{ fontWeight: '600', color: 'var(--primary-color)' }}>
                    {schedulerStatus?.autoApprove ? 'ON' : 'OFF'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: AI Campaign Generator & Post Feed */}
          <div>
            <div className="glass-panel" style={{ padding: '2.5rem', marginBottom: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
                <div>
                  <h3>AI Campaign Generator</h3>
                  <p style={{ color: 'var(--text-muted)' }}>Upload raw media & optional context. Our AI will analyze it, write platform-specific copy, and post or schedule.</p>
                </div>
                <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '0.5rem 1rem', borderRadius: '999px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={16} color="var(--primary-color)" />
                  <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--primary-color)' }}>Context: {activeBusiness?.businessModel || 'AI Tuned'}</span>
                </div>
              </div>
              
              <div className="input-group" style={{ marginBottom: '1.5rem' }}>
                <label style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>Campaign Angle / Topic (Optional)</label>
                <input 
                  type="text"
                  placeholder="e.g. Summer special deal, Product showcase, Behind the scenes"
                  value={baseCaption}
                  onChange={e => setBaseCaption(e.target.value)}
                />
              </div>

              <div 
                className="dropzone" 
                onDragOver={e => e.preventDefault()} 
                onDrop={handleDrop}
                onClick={() => document.getElementById('file-input').click()}
              >
                <UploadCloud className="dropzone-icon" />
                <h4>Drag & Drop media here</h4>
                <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>Supports Images & Videos (Max 50MB)</p>
                <input type="file" id="file-input" multiple accept="image/*,video/*" className="hidden" onChange={handleFileChange} />
              </div>

              {files.length > 0 && (
                <div className="media-grid fade-in" style={{ marginTop: '1rem' }}>
                  {files.map((file, i) => (
                    <div key={i} className="media-item">
                      {file.type.startsWith('image/') ? 
                        <img src={URL.createObjectURL(file)} alt="preview" /> : 
                        <video src={URL.createObjectURL(file)} />
                      }
                      <button style={{ position: 'absolute', top: '0.25rem', right: '0.25rem', background: 'rgba(0,0,0,0.5)', border: 'none', color: 'white', borderRadius: '50%', width: '24px', height: '24px', cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); setFiles(files.filter((_, idx) => idx !== i)); }}>&times;</button>
                    </div>
                  ))}
                </div>
              )}

              <button className="btn btn-primary btn-large" style={{ width: '100%', marginTop: '1.5rem' }} onClick={startAutomation} disabled={loading}>
                <span className="btn-text">Generate & Schedule Campaign</span>
                {loading ? <span className="spinner"></span> : <Send size={18} style={{ marginLeft: '0.5rem' }} />}
              </button>
            </div>

            {/* Live Social Posts Activity Feed */}
            {/* Live Social Posts Activity Feed */}
            {refreshing && recentPosts.length === 0 ? (
              <div className="glass-panel" style={{ padding: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem' }}>Recent Automated Posts</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {Array(3).fill(0).map((_, i) => <div key={i} className="skeleton-card" style={{ height: '90px', borderRadius: '12px' }}></div>)}
                </div>
              </div>
            ) : recentPosts.length > 0 && (
              <div className="glass-panel" style={{ padding: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem' }}>Recent Automated Posts</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {recentPosts.map((post) => (
                    <div key={post.id} style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.85rem', color: 'var(--primary-color)' }}>{post.platform}</span>
                        <span className={`badge ${post.status === 'POSTED' ? 'active' : ''}`} style={{ fontSize: '0.7rem' }}>
                          {post.status}
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-main)' }}>{post.caption}</p>
                      {post.postedAt && (
                        <p style={{ margin: '0.5rem 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Published at: {new Date(post.postedAt).toLocaleString()}
                        </p>
                      )}
                    </div>
                  ))}
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
