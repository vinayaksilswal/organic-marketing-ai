import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE, authFetch } from '../../config';
import { CheckCircle2, Clock, Play, FileText, X, Image as ImageIcon, Video, Send, Settings, Mail, Users, Edit3, AlertTriangle, RefreshCw, CalendarDays } from 'lucide-react';
import PostCalendar from '../../components/PostCalendar';

const SocialScheduler = ({ user, token, showToast, activeWorkspaceId }) => {
  const navigate = useNavigate();
  const [previewTab, setPreviewTab] = useState('feed'); // 'reels' | 'feed' | 'profile'
  const [mediaRatio, setMediaRatio] = useState(null);   // width / height of the attached asset
  const [business, setBusiness] = useState(null);
  const [posts, setPosts] = useState([]);
  const [postsError, setPostsError] = useState(null);
  const [postsLoading, setPostsLoading] = useState(true);
  const [mediaList, setMediaList] = useState([]);
  const [activeTab, setActiveTab] = useState('social'); // 'social', 'email', 'audience'
  
  // Toggles
  const [frequencyHours, setFrequencyHours] = useState(2);
  const [autoApproveActive, setAutoApproveActive] = useState(false);
  const [runningLoop, setRunningLoop] = useState(false);

  // Edit Modal State
  const [editingPost, setEditingPost] = useState(null);
  const [editCaption, setEditCaption] = useState('');
  const [editMedia, setEditMedia] = useState(null);

  useEffect(() => {
    fetchSettings();
    fetchPosts();
    fetchMedia();
    // The preview shows the real business name and handle rather than a
    // hardcoded "Organiflo", so it reflects what will actually be published.
    (async () => {
      try {
        const res = await authFetch(`${API_BASE}/businesses`, {}, token);
        if (!res.ok) return;
        const all = await res.json();
        if (Array.isArray(all)) {
          setBusiness(all.find(b => b.id === activeWorkspaceId) || all[0] || null);
        }
      } catch { /* preview falls back to a neutral placeholder */ }
    })();
  }, [activeWorkspaceId]);

  const fetchSettings = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/settings`, {}, token);
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          setAutoApproveActive(data.autoApprove);
          setFrequencyHours(data.intervalHours);
        }
      }
    } catch (err) { console.error('Failed to fetch settings'); }
  };

  const fetchPosts = async () => {
    setPostsLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts`, {}, token);
      if (res.ok) {
        setPosts(await res.json());
        setPostsError(null);
      } else {
        // A failed request must never be shown as "no posts yet" — that reads
        // as "the automation ran and produced nothing", which is a different
        // and much more alarming problem than "the server errored".
        setPostsError(
          res.status >= 500
            ? `The server could not return your delivery log (error ${res.status}).`
            : `Could not load your delivery log (error ${res.status}).`
        );
      }
    } catch (err) {
      console.error('Failed to fetch posts', err);
      setPostsError('Could not reach the server to load your delivery log.');
    } finally {
      setPostsLoading(false);
    }
  };
  
  const fetchMedia = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/media`, {}, token);
      if (res.ok) setMediaList(await res.json());
    } catch (err) { console.error('Failed to fetch media'); }
  };

  const handleFrequencyChange = async (hours) => {
    setFrequencyHours(hours);
    try {
      await authFetch(`${API_BASE}/marketing/settings/interval`, {
        method: 'POST',
        body: JSON.stringify({ intervalHours: hours })
      }, token);
      showToast('Frequency updated successfully');
    } catch (err) {
      console.error('Failed to update frequency', err);
    }
  };

  const handleAutoApproveChange = async (isActive) => {
    setAutoApproveActive(isActive);
    try {
      await authFetch(`${API_BASE}/marketing/settings/auto-approve`, {
        method: 'POST',
        body: JSON.stringify({ autoApprove: isActive })
      }, token);
      showToast('Auto-Approve updated successfully');
    } catch (err) {
      console.error('Failed to update auto-approve', err);
    }
  };

  const handleRunAutomation = async () => {
    setRunningLoop(true);
    showToast('Running AI Automation...', false);
    try {
      const res = await authFetch(`${API_BASE}/marketing/run-automation`, { method: 'POST' }, token);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success) {
        showToast('Automation Loop Completed! 🚀');
        if (data.post) {
          setPosts(prev => [data.post, ...prev]);
        } else {
          fetchPosts(); // fallback refresh
        }
      } else {
        // Surface why. "Automation Failed" gave the user nothing to act on —
        // a server fault and "no media to post" need different responses.
        const reason = data.detail || data.message
          || (res.status >= 500
                ? `the server returned error ${res.status}`
                : `the request was rejected (${res.status})`);
        showToast(`Automation did not run — ${reason}`, true);
      }
    } catch (err) {
      console.error(err);
      showToast(`Could not run automation — ${err.message}`, true);
    } finally {
      setRunningLoop(false);
    }
  };

  const handleEditDraft = (post) => {
    setEditingPost(post);
    setEditCaption(post.caption || '');
    setEditMedia(post.mediaUrls?.[0] || null);
  };

  const handleSaveDraft = async () => {
    if (editCaption && editCaption.length > 2200) {
      showToast('Caption exceeds Instagram limit of 2200 characters', true);
      return;
    }
    try {
      const formData = new FormData();
      formData.append('caption', editCaption);
      formData.append('status', 'DRAFT');
      if (editMedia) formData.append('existing_media', editMedia);

      const res = await authFetch(`${API_BASE}/marketing/posts/${editingPost.id}`, {
        method: 'PUT',
        body: formData,
        isFormData: true
      }, token);
      
      if (res.ok) {
        const updatedPost = await res.json();
        setPosts(prev => prev.map(p => p.id === editingPost.id ? updatedPost : p));
        showToast('Draft Saved successfully!');
        setEditingPost(null);
      } else {
        showToast('Failed to save draft', true);
      }
    } catch (err) {
      console.error(err);
      showToast('Failed to save draft', true);
    }
  };

  const handleUpdateLive = async () => {
    if (editCaption && editCaption.length > 2200) {
      showToast('Caption exceeds Instagram limit of 2200 characters', true);
      return;
    }
    try {
      const formData = new FormData();
      formData.append('caption', editCaption);
      formData.append('status', 'POSTED');
      if (editMedia) formData.append('existing_media', editMedia);

      const res = await authFetch(`${API_BASE}/marketing/posts/${editingPost.id}`, {
        method: 'PUT',
        body: formData,
        isFormData: true
      }, token);
      
      if (res.ok) {
        const updatedPost = await res.json();
        setPosts(prev => prev.map(p => p.id === editingPost.id ? updatedPost : p));
        showToast('Post successfully published! 🚀');
        setEditingPost(null);
      } else {
        showToast('Failed to publish post', true);
      }
    } catch (err) {
      console.error(err);
      showToast('Failed to publish post', true);
    }
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        
        {/* HEADER SECTION */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem', background: 'rgba(11, 16, 32, 0.03)', padding: '1.5rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.75rem' }}>Social Scheduler</h1>
            <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
              Configure AI publishing frequency and monitor automated delivery logs.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Posting frequency is owned by Businesses -> Edit -> Automation.
                Two controls writing the same setting was a source of confusion
                about which one actually applied. */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(0,0,0,0.3)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <Clock size={15} className="text-muted" />
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Posts every <strong style={{ color: 'var(--text-main)' }}>{frequencyHours}h</strong>
              </span>
              <button
                onClick={() => navigate('/dashboard/workspaces')}
                style={{ background: 'none', border: 'none', padding: 0, color: 'var(--primary-color)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}
              >
                Change
              </button>
            </div>

            {/* Auto Approve Toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(0,0,0,0.3)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <label style={{ position: 'relative', display: 'inline-block', width: '40px', height: '22px' }}>
                 <input type="checkbox" checked={autoApproveActive} onChange={(e) => handleAutoApproveChange(e.target.checked)} style={{ opacity: 0, width: 0, height: 0 }} />
                <span style={{ position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: autoApproveActive ? 'var(--success)' : 'rgba(255,255,255,0.2)', transition: '.4s', borderRadius: '34px' }}>
                  <span style={{ position: 'absolute', content: '""', height: '14px', width: '14px', left: autoApproveActive ? '22px' : '4px', bottom: '4px', backgroundColor: 'white', transition: '.4s', borderRadius: '50%' }}></span>
                </span>
              </label>
              <span style={{ fontSize: '0.85rem', fontWeight: '600' }}>Auto-Approve</span>
            </div>

            {/* Run Automation Button */}
            <button 
              className="btn btn-primary" 
              onClick={handleRunAutomation}
              disabled={runningLoop}
              style={{ background: '#3b82f6', color: '#fff', fontWeight: '600', padding: '0.6rem 1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {runningLoop ? <span className="spinner"></span> : <>⚡ Run Automation</>}
            </button>
          </div>
        </div>

        {/* SCHEDULE — the month, with every post on the day it went out.
            A table answers "what happened last?"; the questions people
            actually have about a schedule are shape questions: is anything
            going out tomorrow, did Tuesday publish, why is there a gap. */}
        <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem', border: '1px solid var(--border-color)', boxShadow: 'none', background: 'rgba(11, 16, 32, 0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
            <CalendarDays size={18} color="var(--primary-color)" />
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Posting calendar</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Click any post to preview or edit it
            </span>
          </div>
          {postsLoading ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Loading the schedule…</p>
          ) : (
            <PostCalendar posts={posts} onSelect={handleEditDraft} />
          )}
        </div>

        {/* LOGS SECTION */}
        <div className="glass-panel" style={{ overflow: 'hidden', border: '1px solid var(--border-color)', boxShadow: 'none', background: 'rgba(11, 16, 32, 0.02)' }}>
          <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
             <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Automation Logs</h2>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                <th style={{ padding: '1rem 1.5rem', fontWeight: '700' }}>Status</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: '700' }}>Platform</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: '700' }}>Scheduled Time</th>
                <th style={{ padding: '1rem 1.5rem', fontWeight: '700', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {postsLoading ? (
                <tr>
                  <td colSpan="4" style={{ padding: '3rem', textAlign: 'center' }}>
                    <span className="spinner" style={{ width: 20, height: 20 }} />
                  </td>
                </tr>
              ) : postsError ? (
                <tr>
                  <td colSpan="4" style={{ padding: '2.5rem', textAlign: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                      <AlertTriangle size={22} color="#f87171" />
                      <div style={{ color: '#fca5a5', fontSize: '0.9rem', maxWidth: 480, lineHeight: 1.55 }}>
                        {postsError} This is a server fault, not an empty schedule — your automation
                        history could not be read.
                      </div>
                      <button className="btn btn-secondary" onClick={fetchPosts}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.45rem 0.9rem', fontSize: '0.83rem' }}>
                        <RefreshCw size={14} /> Retry
                      </button>
                    </div>
                  </td>
                </tr>
              ) : posts.length === 0 ? (
                <tr>
                  <td colSpan="4" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No posts logged yet. Connect a social account and run the automation loop.
                  </td>
                </tr>
              ) : (
                posts.map(post => (
                  <tr key={post.id} style={{ borderBottom: '1px solid rgba(11, 16, 32, 0.05)' }}>
                    <td style={{ padding: '1rem 1.5rem', verticalAlign: 'top' }}>
                      {/* Never invent a status. This used to render POSTED for
                          any row with no status, which read as a success that
                          had not happened. */}
                      <span style={{
                        fontSize: '0.75rem', fontWeight: '700', padding: '0.3rem 0.7rem',
                        borderRadius: '30px',
                        background: post.status === 'POSTED' ? 'rgba(16,185,129,0.15)'
                          : post.status === 'FAILED' ? 'rgba(239,68,68,0.15)'
                          : 'rgba(245,158,11,0.15)',
                        color: post.status === 'POSTED' ? 'var(--success)'
                          : post.status === 'FAILED' ? '#f87171'
                          : '#f59e0b',
                      }}>
                        {post.status || 'UNKNOWN'}
                      </span>

                      {/* The reason a delivery failed. Recorded all along,
                          never shown — so every failure looked identical. */}
                      {post.status === 'FAILED' && post.errorLog && (
                        <div style={{
                          marginTop: '0.55rem', maxWidth: 340, padding: '0.5rem 0.65rem',
                          borderRadius: 7, background: 'rgba(239,68,68,0.07)',
                          border: '1px solid rgba(239,68,68,0.2)',
                        }}>
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.35rem' }}>
                            <AlertTriangle size={12} color="#f87171" style={{ flexShrink: 0, marginTop: 2 }} />
                            <p style={{ margin: 0, fontSize: '0.72rem', lineHeight: 1.5, color: '#fca5a5', wordBreak: 'break-word' }}>
                              {post.errorLog}
                            </p>
                          </div>
                        </div>
                      )}
                      {post.status === 'FAILED' && !post.errorLog && (
                        <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.72rem', color: 'var(--text-muted)', maxWidth: 300, lineHeight: 1.5 }}>
                          No reason was recorded for this failure.
                        </p>
                      )}
                    </td>
                    <td style={{ padding: '1rem 1.5rem', fontWeight: '600', fontSize: '0.9rem', verticalAlign: 'top' }}>
                      {post.platform || '—'}
                      {(post.fbPostId || post.igPostId) && (
                        <div style={{ marginTop: '0.3rem', fontSize: '0.68rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                          {post.fbPostId ? 'FB ✓' : ''} {post.igPostId ? 'IG ✓' : ''}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '1rem 1.5rem', fontSize: '0.9rem' }}>
                      {post.scheduledAt ? new Date(post.scheduledAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : new Date().toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                    </td>
                    <td style={{ padding: '1rem 1.5rem', textAlign: 'right' }}>
                      <button 
                        className="btn btn-secondary" 
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }} 
                        onClick={() => handleEditDraft(post)}
                      >
                        {post.status === 'POSTED' ? 'View Details' : 'Edit / Preview'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* SIDE-BY-SIDE EDIT MODAL */}
        {editingPost && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ width: '100%', maxWidth: '1000px', height: '80vh', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
              
              {/* Header */}
              <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', background: 'var(--bg-card-hover)' }}>
                <button onClick={() => setEditingPost(null)} style={{ border: 'none', color: 'var(--text-main)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(11, 16, 32, 0.06)', borderRadius: '50%', padding: '0.3rem', marginRight: '1rem' }}>
                  <X size={16} />
                </button>
                <div style={{ background: 'var(--secondary-color)', width: '24px', height: '24px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '0.5rem' }}>
                  <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '12px' }}>f</span>
                </div>
                <h3 style={{ margin: 0, fontSize: '1rem' }}>Edit Draft / Post</h3>
              </div>

              {/* Body */}
              <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                
                {/* Left Side: Editor */}
                <div style={{ flex: 1, padding: '1.5rem', borderRight: '1px solid var(--border-color)', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  <textarea 
                    rows="8" 
                    value={editCaption} 
                    onChange={(e) => setEditCaption(e.target.value)} 
                    style={{ width: '100%', padding: '1rem', borderRadius: '8px', background: 'rgba(11, 16, 32, 0.03)', border: '1px solid var(--border-color)', color: 'var(--text-main)', resize: 'vertical', fontSize: '0.9rem', lineHeight: 1.5 }}
                  />
                  <div style={{ textAlign: 'right', fontSize: '0.8rem', color: editCaption.length > 2200 ? 'var(--danger)' : 'var(--text-muted)', marginTop: '-1rem' }}>
                    {editCaption.length} / 2200 characters
                  </div>
                  
                  <div>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: '600' }}>Media (Image/Video)</label>
                    <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(11, 16, 32, 0.03)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem' }}>
                      <input 
                        type="file" 
                        accept="image/*,video/*"
                        onChange={(e) => {
                          if (e.target.files[0]) {
                            const file = e.target.files[0];
                            setEditMedia(URL.createObjectURL(file));
                            if (file.type.startsWith('video/')) {
                              showToast('Tip: For best results on Reels/TikTok, use 9:16 aspect ratio (1080x1920)', false);
                            } else if (file.type.startsWith('image/')) {
                              showToast('Tip: Instagram supports 1:1, 4:5, or 1.91:1 ratios', false);
                            }
                          }
                        }}
                        style={{ fontSize: '0.85rem', width: '100%', color: 'var(--text-muted)' }} 
                      />
                    </div>
                  </div>

                  {editMedia && (
                    <div style={{ width: '100px', height: '100px', borderRadius: '8px', overflow: 'hidden', background: '#000' }}>
                       {editMedia.includes('video') || editMedia.endsWith('.mp4') ? (
                          <video src={editMedia} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : (
                          <img src={editMedia} alt="Media" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        )}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '1rem', marginTop: 'auto' }}>
                    {editingPost.status === 'DRAFT' ? (
                      <>
                        <button className="btn btn-secondary" style={{ flex: 1, padding: '0.75rem' }} onClick={handleSaveDraft}>Save Draft</button>
                        <button className="btn btn-primary" style={{ flex: 2, padding: '0.75rem', background: '#3b82f6', color: '#fff', border: 'none' }} onClick={handleUpdateLive}>Post Now 🚀</button>
                      </>
                    ) : (
                      <button className="btn btn-secondary" style={{ flex: 1, padding: '0.75rem' }} onClick={() => setEditingPost(null)}>Close View</button>
                    )}
                  </div>
                </div>

                {/* Right Side: Preview */}
                <div style={{ flex: 1, padding: '1.5rem', background: 'rgba(0,0,0,0.5)', overflowY: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  
                  {(() => {
                    const isVideo = !!editMedia && (editMedia.includes('video') || /\.(mp4|mov|webm)$/i.test(editMedia));
                    const handle = (business?.name || 'yourbrand').toLowerCase().replace(/[^a-z0-9]/g, '');
                    // Real Instagram surfaces: Reels 9:16, Feed 4:5, Profile 1:1 grid.
                    const ratio = previewTab === 'reels' ? '9/16' : previewTab === 'profile' ? '1/1' : '4/5';
                    // Match what each surface actually does. Reels letterboxes
                    // anything that is not 9:16; Feed and the profile grid crop
                    // to fill. Using one mode everywhere misrepresented both.
                    const fit = previewTab === 'reels' ? 'contain' : 'cover';

                    // Natural dimensions drive the warning below, so the user
                    // learns before posting that a landscape clip will be
                    // pillarboxed in Reels or cropped in the grid.
                    const onMeta = (e) => {
                      const el = e.currentTarget;
                      const w = el.videoWidth || el.naturalWidth;
                      const h = el.videoHeight || el.naturalHeight;
                      if (w && h) setMediaRatio(w / h);
                    };

                    const mediaEl = !editMedia ? (
                      <div style={{ color: 'var(--text-muted)', textAlign: 'center' }}>
                        <Video size={30} style={{ opacity: 0.5, marginBottom: '0.5rem' }} />
                        <p style={{ margin: 0, fontSize: '0.8rem' }}>No media attached</p>
                      </div>
                    ) : isVideo ? (
                      <video src={editMedia} controls playsInline preload="metadata" onLoadedMetadata={onMeta}
                        style={{ width: '100%', height: '100%', objectFit: fit, background: '#000' }} />
                    ) : (
                      <img src={editMedia} alt="Preview" onLoad={onMeta}
                        style={{ width: '100%', height: '100%', objectFit: fit, background: '#000' }} />
                    );

                    // What this surface will do to this specific asset.
                    let fitNote = null;
                    if (mediaRatio) {
                      const shape = mediaRatio > 1.15 ? 'landscape' : mediaRatio < 0.85 ? 'portrait' : 'square';
                      if (previewTab === 'reels' && shape !== 'portrait') {
                        fitNote = `${shape} media — Reels will show bars around it. 9:16 fills the screen.`;
                      } else if (previewTab === 'feed' && shape === 'landscape') {
                        fitNote = 'Landscape media — the feed crops the top and bottom to 4:5.';
                      } else if (previewTab === 'profile' && shape !== 'square') {
                        fitNote = `${shape} media — the grid centre-crops it to a square.`;
                      }
                    }

                    return (
                      <>
                        <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1.25rem', background: 'rgba(11, 16, 32, 0.08)', padding: '0.25rem', borderRadius: '30px' }}>
                          {[['reels', 'Reels'], ['feed', 'Feed'], ['profile', 'Profile']].map(([k, label]) => (
                            <button key={k} onClick={() => setPreviewTab(k)}
                              style={{
                                padding: '0.4rem 1.1rem', borderRadius: '20px', border: 'none', cursor: 'pointer',
                                fontWeight: 600, fontSize: '0.85rem',
                                background: previewTab === k ? 'var(--secondary-color)' : 'transparent',
                                color: previewTab === k ? '#fff' : 'var(--text-muted)',
                              }}>
                              {label}
                            </button>
                          ))}
                        </div>

                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.75rem', textAlign: 'center' }}>
                          {previewTab === 'reels' ? '9:16 — full screen'
                            : previewTab === 'profile' ? '1:1 — grid thumbnail'
                            : '4:5 — feed post'}
                        </div>

                        {fitNote && (
                          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem', maxWidth: 330, marginBottom: '0.85rem', padding: '0.5rem 0.7rem', borderRadius: 8, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
                            <AlertTriangle size={12} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
                            <span style={{ fontSize: '0.72rem', color: '#fcd34d', lineHeight: 1.45 }}>{fitNote}</span>
                          </div>
                        )}

                        {previewTab === 'profile' ? (
                          /* Profile grid: how it sits among other posts */
                          <div style={{ width: '100%', maxWidth: 330, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 3 }}>
                            <div style={{ aspectRatio: '1/1', background: '#000', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '2px solid var(--secondary-color)' }}>
                              {mediaEl}
                            </div>
                            {Array.from({ length: 8 }).map((_, i) => (
                              <div key={i} style={{ aspectRatio: '1/1', background: 'rgba(11, 16, 32, 0.04)' }} />
                            ))}
                          </div>
                        ) : previewTab === 'reels' ? (
                          /* Reels: caption overlays the video, as it does on Instagram */
                          <div style={{ width: '100%', maxWidth: 260, aspectRatio: '9/16', background: '#000', borderRadius: 14, overflow: 'hidden', position: 'relative', border: '1px solid var(--border-color)' }}>
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{mediaEl}</div>
                            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '0.85rem', background: 'linear-gradient(transparent, rgba(0,0,0,0.85))' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                                <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'linear-gradient(135deg,var(--primary-color),var(--secondary-color))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700 }}>
                                  {(business?.name || 'B').charAt(0).toUpperCase()}
                                </div>
                                <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>{handle}</span>
                              </div>
                              <p style={{ margin: 0, fontSize: '0.72rem', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                {editCaption || 'Your caption will appear here'}
                              </p>
                            </div>
                          </div>
                        ) : (
                          /* Feed post */
                          <div style={{ width: '100%', maxWidth: 350, background: '#111', borderRadius: 12, border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                            <div style={{ padding: '0.7rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                              <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg,var(--primary-color),var(--secondary-color))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.8rem' }}>
                                {(business?.name || 'B').charAt(0).toUpperCase()}
                              </div>
                              <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{handle}</span>
                              <div style={{ marginLeft: 'auto', display: 'flex', gap: 3 }}>
                                {[0, 1, 2].map(i => <div key={i} style={{ width: 3.5, height: 3.5, background: 'var(--text-muted)', borderRadius: '50%' }} />)}
                              </div>
                            </div>

                            <div style={{ width: '100%', aspectRatio: ratio, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              {mediaEl}
                            </div>

                            <div style={{ padding: '0.7rem 0.75rem' }}>
                              <div style={{ display: 'flex', gap: '0.9rem', marginBottom: '0.5rem', color: 'var(--text-main)' }}>
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                              </div>
                              <p style={{ margin: 0, fontSize: '0.83rem', lineHeight: 1.45, whiteSpace: 'pre-wrap' }}>
                                <span style={{ fontWeight: 600, marginRight: '0.4rem' }}>{handle}</span>
                                {editCaption || 'Your caption will appear here'}
                              </p>
                            </div>
                          </div>
                        )}
                      </>
                    );
                  })()}

                </div>
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default SocialScheduler;
