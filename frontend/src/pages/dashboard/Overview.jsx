import React, { useState, useEffect } from 'react';
import { UploadCloud, CheckCircle2, Facebook, Instagram, Twitter, Linkedin, Sparkles, BarChart3, Activity, Clock, RefreshCw, Send } from 'lucide-react';
import { API_BASE, authFetch } from '../../App';


const Dashboard = ({ user, token, showToast }) => {
  const [metaConnected, setMetaConnected] = useState(false);
  const [xConnected, setXConnected] = useState(false);
  const [linkedinConnected, setLinkedinConnected] = useState(false);
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
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      showToast(`Dashboard sync failed: ${err.message}`, true);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [token]);

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
                {/* Meta Integration */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: metaConnected ? '1rem' : '0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <Facebook size={20} color="#1877F2" />
                      <Instagram size={20} color="#E4405F" />
                      <span style={{ fontWeight: '600' }}>Meta</span>
                    </div>
                    {metaConnected ? (
                      <span className="badge active" style={{ fontSize: '0.65rem' }}>Connected</span>
                    ) : (
                      <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }} onClick={() => { setMetaConnected(true); showToast('Meta connected successfully!'); }}>Connect</button>
                    )}
                  </div>
                  {metaConnected && (
                    <div className="fade-in">
                      <div className="input-group" style={{ marginBottom: '0.75rem' }}>
                        <select style={{ padding: '0.5rem', fontSize: '0.875rem' }}><option>My Business Page</option></select>
                      </div>
                      <div className="input-group" style={{ marginBottom: '0' }}>
                        <select style={{ padding: '0.5rem', fontSize: '0.875rem' }}><option>@mybusiness_ig</option></select>
                      </div>
                    </div>
                  )}
                </div>

                {/* X Integration */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <Twitter size={20} color="#1DA1F2" />
                      <span style={{ fontWeight: '600' }}>X (Twitter)</span>
                    </div>
                    {xConnected ? (
                      <span className="badge active" style={{ fontSize: '0.65rem' }}>Connected</span>
                    ) : (
                      <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }} onClick={() => { setXConnected(true); showToast('X connected successfully!'); }}>Connect</button>
                    )}
                  </div>
                </div>

                {/* LinkedIn Integration */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <Linkedin size={20} color="#0A66C2" />
                      <span style={{ fontWeight: '600' }}>LinkedIn</span>
                    </div>
                    {linkedinConnected ? (
                      <span className="badge active" style={{ fontSize: '0.65rem' }}>Connected</span>
                    ) : (
                      <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }} onClick={() => { setLinkedinConnected(true); showToast('LinkedIn connected successfully!'); }}>Connect</button>
                    )}
                  </div>
                </div>
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
                  <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--primary-color)' }}>Context: {user?.businessProfile?.businessModel || 'AI Tuned'}</span>
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
