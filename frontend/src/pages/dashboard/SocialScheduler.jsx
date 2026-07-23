import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { Calendar, Clock, Edit3, Trash2, CheckCircle2, XCircle, Play, AlertCircle, RefreshCw, X, FileText, Send, Sparkles, Image as ImageIcon } from 'lucide-react';

const SocialScheduler = ({ user, token, showToast, activeWorkspaceId }) => {
  const [posts, setPosts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [creatives, setCreatives] = useState([]);
  const [intervalHrs, setIntervalHrs] = useState(2); // 2hr Default
  const [autoApprove, setAutoApprove] = useState(false);
  const [customHrs, setCustomHrs] = useState('');
  const [isCustom, setIsCustom] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [runningLoop, setRunningLoop] = useState(false);
  const [activeTab, setActiveTab] = useState('queue'); // 'queue', 'creatives', or 'logs'
  const [brandStatus, setBrandStatus] = useState(null);

  // Post edit modal state
  const [editingPost, setEditingPost] = useState(null);
  const [editCaption, setEditCaption] = useState('');
  const [editScheduledAt, setEditScheduledAt] = useState('');
  const [editStatus, setEditStatus] = useState('SCHEDULED');
  const [editSubmitting, setEditSubmitting] = useState(false);

  useEffect(() => {
    fetchPosts();
    fetchLogs();
    fetchCreatives();
    fetchBrandStatus();
  }, [activeWorkspaceId]);

  const fetchPosts = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts`, {}, token);
      if (res.ok) setPosts(await res.json());
    } catch (err) { console.error(err); }
  };

  const fetchLogs = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/logs`, {}, token);
      if (res.ok) setLogs(await res.json());
    } catch (err) { console.error(err); }
  };

  const fetchCreatives = async () => {
    try {
      const res = await authFetch(`${API_BASE}/creatives/queue`, {}, token);
      if (res.ok) {
        const data = await res.json();
        setCreatives(data.data || []);
      }
    } catch (err) { console.error(err); }
  };

  const fetchBrandStatus = async () => {
    try {
      const res = await authFetch(`${API_BASE}/creatives/brand-status`, {}, token);
      if (res.ok) setBrandStatus(await res.json());
    } catch (err) { console.error(err); }
  };

  const toggleAutoApprove = async () => {
    const newValue = !autoApprove;
    try {
      const res = await authFetch(`${API_BASE}/marketing/settings/auto-approve`, {
        method: 'POST',
        body: JSON.stringify({ autoApprove: newValue })
      }, token);
      if (res.ok) {
        setAutoApprove(newValue);
        showToast(newValue ? 'Auto-Approve Enabled' : 'Auto-Approve Disabled');
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const saveInterval = async (val) => {
    const hours = val || (isCustom ? parseInt(customHrs) : intervalHrs);
    if (!hours || hours < 1) return showToast('Please select or enter valid hours', true);
    
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/settings/interval`, {
        method: 'POST',
        body: JSON.stringify({ intervalHours: hours })
      }, token);
      if (res.ok) {
        setIntervalHrs(hours);
        showToast(`Posting interval set to every ${hours} hour(s)!`);
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  const runAutomationNow = async () => {
    setRunningLoop(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/run-automation`, { method: 'POST' }, token);
      if (res.ok) {
        showToast('Marketing automation loop executed successfully! 🚀');
        fetchPosts();
        fetchLogs();
      } else throw new Error('Execution failed');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setRunningLoop(false);
    }
  };

  const generateNewCreatives = async () => {
    setGenerating(true);
    showToast('AI is generating new creatives and images... this may take a minute.', false);
    try {
      const res = await authFetch(`${API_BASE}/creatives/generate`, {
        method: 'POST',
        body: JSON.stringify({ count: 3 })
      }, token);
      if (res.ok) {
        const data = await res.json();
        showToast(`Successfully generated ${data.count} new creatives!`);
        fetchCreatives();
        setActiveTab('creatives');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setGenerating(false);
    }
  };

  const updateCreativeStatus = async (id, isApprove) => {
    try {
      const endpoint = isApprove ? 'approve' : 'reject';
      const res = await authFetch(`${API_BASE}/creatives/${id}/${endpoint}`, { method: 'POST' }, token);
      if (res.ok) {
        showToast(`Creative ${isApprove ? 'approved' : 'rejected'}`);
        fetchCreatives();
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const openEditModal = (post) => {
    setEditingPost(post);
    setEditCaption(post.caption || '');
    setEditStatus(post.status || 'SCHEDULED');
    setEditScheduledAt(post.scheduledAt ? new Date(post.scheduledAt).toISOString().slice(0, 16) : '');
  };

  const handleUpdatePost = async () => {
    if (!editingPost) return;
    setEditSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('caption', editCaption);
      formData.append('status', editStatus);
      if (editScheduledAt) formData.append('scheduledAt', new Date(editScheduledAt).toISOString());

      const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
      const res = await fetch(`${API_BASE}/marketing/posts/${editingPost.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          ...(activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {})
        },
        body: formData
      });

      if (res.ok) {
        showToast('Social post updated!');
        setEditingPost(null);
        fetchPosts();
      } else throw new Error('Failed to update post');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setEditSubmitting(false);
    }
  };

  const presets = [2, 4, 8, 12, 24];
  const pendingCreatives = creatives.filter(c => !c.isActive);
  const activeCreatives = creatives.filter(c => c.isActive);

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <Send color="var(--primary-color)" size={32} /> Social Media Automation
            </h1>
            <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
              Manage your AI-generated creatives, configure publishing frequency, and monitor automated delivery.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button className="btn btn-secondary" onClick={generateNewCreatives} disabled={generating} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {generating ? <span className="spinner"></span> : <><Sparkles size={18} /> Generate AI Creatives</>}
            </button>
            <button className="btn btn-primary" onClick={runAutomationNow} disabled={runningLoop} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {runningLoop ? <span className="spinner"></span> : <><Play size={18} /> Run Automation Loop</>}
            </button>
          </div>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '2rem' }}>
          {/* Settings Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {/* Auto-Approve Toggle */}
            <div className="glass-panel" style={{ padding: '2rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem', fontSize: '1.15rem' }}>
                <CheckCircle2 size={20} color="var(--success)" /> Autopilot Mode
              </h3>
              <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.85rem', lineHeight: 1.5 }}>
                When enabled, AI-generated creatives are automatically approved and added to the publishing queue without manual review.
              </p>
              
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontWeight: '600' }}>Auto-Approve</span>
                <label style={{ position: 'relative', display: 'inline-block', width: '50px', height: '26px' }}>
                  <input type="checkbox" checked={autoApprove} onChange={toggleAutoApprove} style={{ opacity: 0, width: 0, height: 0 }} />
                  <span style={{
                    position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: autoApprove ? 'var(--primary-color)' : 'rgba(255,255,255,0.2)',
                    transition: '.4s', borderRadius: '34px'
                  }}>
                    <span style={{
                      position: 'absolute', content: '""', height: '18px', width: '18px',
                      left: autoApprove ? '28px' : '4px', bottom: '4px', backgroundColor: 'white',
                      transition: '.4s', borderRadius: '50%'
                    }}></span>
                  </span>
                </label>
              </div>
            </div>

            {/* Frequency Controls */}
            <div className="glass-panel" style={{ padding: '2rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem', fontSize: '1.15rem' }}>
                <Clock size={20} color="var(--primary-color)" /> Frequency Controls
              </h3>
              <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.85rem', lineHeight: 1.5 }}>
                Select how often the autonomous loop publishes content for this brand.
              </p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
                {presets.map(hrs => (
                  <button
                    key={hrs}
                    className={`btn ${intervalHrs === hrs && !isCustom ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ justifyContent: 'space-between', padding: '0.6rem 1rem' }}
                    onClick={() => { setIsCustom(false); saveInterval(hrs); }}
                  >
                    <span>Every {hrs} Hours</span>
                    {hrs === 2 && <span style={{ fontSize: '0.7rem', background: 'var(--primary-color)', color: '#fff', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: '700' }}>DEFAULT</span>}
                  </button>
                ))}

                <button
                  className={`btn ${isCustom ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ justifyContent: 'space-between', padding: '0.6rem 1rem' }}
                  onClick={() => setIsCustom(true)}
                >
                  <span>Custom Interval...</span>
                </button>
              </div>

              {isCustom && (
                <div className="fade-in" style={{ marginBottom: '1.25rem' }}>
                  <div className="input-group">
                    <label>Custom Hours</label>
                    <input 
                      type="number" min="1" placeholder="e.g. 6" 
                      value={customHrs} onChange={(e) => setCustomHrs(e.target.value)} 
                    />
                  </div>
                  <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => saveInterval()} disabled={loading}>
                    {loading ? <span className="spinner"></span> : 'Set Custom Interval'}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Queue & Logs Area */}
          <div className="glass-panel" style={{ padding: '2rem', height: 'fit-content' }}>
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
              <button 
                className={`btn ${activeTab === 'creatives' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('creatives')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <ImageIcon size={18} /> Creatives ({pendingCreatives.length})
              </button>
              <button 
                className={`btn ${activeTab === 'queue' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('queue')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <Calendar size={18} /> Publishing Queue ({posts.length})
              </button>
              <button 
                className={`btn ${activeTab === 'logs' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('logs')}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <FileText size={18} /> Audit Logs
              </button>
            </div>

            {/* Creatives Tab */}
            {activeTab === 'creatives' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={{ margin: 0 }}>Pending Approval ({pendingCreatives.length})</h4>
                </div>
                
                {pendingCreatives.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                    No pending creatives. Click "Generate AI Creatives" to create more content.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1.5rem' }}>
                    {pendingCreatives.map(creative => (
                      <div key={creative.id} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '12px', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                        {creative.mediaUrl && (
                          <div style={{ width: '100%', height: '180px', background: '#000' }}>
                            <img src={creative.mediaUrl} alt="AI Creative" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          </div>
                        )}
                        <div style={{ padding: '1rem' }}>
                          <p style={{ fontSize: '0.9rem', lineHeight: 1.5, margin: '0 0 1rem 0' }}>{creative.caption}</p>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button className="btn btn-secondary" style={{ flex: 1, padding: '0.5rem', color: 'var(--error)', borderColor: 'rgba(239, 68, 68, 0.3)' }} onClick={() => updateCreativeStatus(creative.id, false)}>
                              Reject
                            </button>
                            <button className="btn btn-primary" style={{ flex: 1, padding: '0.5rem', background: 'var(--success)' }} onClick={() => updateCreativeStatus(creative.id, true)}>
                              Approve
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                <h4 style={{ margin: '2rem 0 0 0', borderTop: '1px solid var(--border-color)', paddingTop: '2rem' }}>Approved Campaigns ({activeCreatives.length})</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {activeCreatives.slice(0, 5).map(creative => (
                    <div key={creative.id} style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      {creative.mediaUrl && <img src={creative.mediaUrl} style={{ width: '60px', height: '60px', borderRadius: '8px', objectFit: 'cover' }} />}
                      <p style={{ margin: 0, fontSize: '0.9rem', flex: 1 }}>{creative.caption}</p>
                      <span className="badge active">APPROVED</span>
                    </div>
                  ))}
                  {activeCreatives.length > 5 && <p style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>+ {activeCreatives.length - 5} more</p>}
                </div>
              </div>
            )}

            {/* Content Queue Tab */}
            {activeTab === 'queue' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {posts.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                    No posts currently queued. Approve creatives or run the automation loop.
                  </div>
                ) : (
                  posts.map(post => (
                    <div key={post.id} style={{ background: 'rgba(0,0,0,0.3)', padding: '1.25rem', borderRadius: '14px', border: '1px solid var(--border-color)', display: 'flex', justify: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                          <span className={`badge ${post.status === 'POSTED' ? 'active' : ''}`} style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>{post.status}</span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--primary-color)', fontWeight: '600' }}>{post.platform || 'FACEBOOK & INSTAGRAM'}</span>
                        </div>
                        <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.95rem', lineHeight: 1.5 }}>{post.caption}</p>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Scheduled: {post.scheduledAt ? new Date(post.scheduledAt).toLocaleString() : 'Pending'}
                          {post.postedAt && ` • Published: ${new Date(post.postedAt).toLocaleString()}`}
                        </p>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-secondary" style={{ padding: '0.5rem' }} onClick={() => openEditModal(post)} title="Edit Post">
                          <Edit3 size={16} />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Audit Logs Tab */}
            {activeTab === 'logs' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {logs.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                    No execution audit logs found. Trigger an automation loop to see real-time delivery logs.
                  </div>
                ) : (
                  logs.map(log => (
                    <div key={log.id} style={{ background: 'rgba(0,0,0,0.3)', padding: '1.25rem', borderRadius: '14px', border: '1px solid var(--border-color)', display: 'flex', justify: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.4rem' }}>
                          <span style={{ background: log.status === 'SUCCESS' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)', color: log.status === 'SUCCESS' ? 'var(--success)' : 'var(--error)', padding: '0.2rem 0.6rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: '700' }}>
                            {log.status}
                          </span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{log.createdAt ? new Date(log.createdAt).toLocaleString() : ''}</span>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          Social Success: {log.socialSuccess ? 'Yes' : 'No'} | Emails Sent: {log.emailCount}
                        </p>
                        {log.errorLog && <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.8rem', color: 'var(--error)' }}>Log detail: {log.errorLog}</p>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

          </div>
        </div>

        {/* Edit Post Modal */}
        {editingPost && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '560px', width: '100%', padding: '2rem', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>Edit Scheduled Post</h3>
                <button onClick={() => setEditingPost(null)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}><X size={20} /></button>
              </div>
              <div className="input-group">
                <label>Post Caption</label>
                <textarea rows="5" value={editCaption} onChange={(e) => setEditCaption(e.target.value)} />
              </div>
              <div className="input-group">
                <label>Scheduled Date & Time</label>
                <input type="datetime-local" value={editScheduledAt} onChange={(e) => setEditScheduledAt(e.target.value)} />
              </div>
              <div className="input-group">
                <label>Post Status</label>
                <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}>
                  <option value="DRAFT">DRAFT</option>
                  <option value="SCHEDULED">SCHEDULED</option>
                  <option value="POSTED">POSTED (Trigger Immediate Publish)</option>
                </select>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>
                <button className="btn btn-secondary" onClick={() => setEditingPost(null)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleUpdatePost} disabled={editSubmitting}>
                  {editSubmitting ? <span className="spinner"></span> : 'Save Post Changes'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SocialScheduler;
