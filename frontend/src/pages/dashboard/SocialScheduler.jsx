import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { CheckCircle2, Clock, Play, FileText, X, Image as ImageIcon, Video, Send, Settings, Mail, Users, Edit3 } from 'lucide-react';

const SocialScheduler = ({ user, token, showToast, activeWorkspaceId }) => {
  const [posts, setPosts] = useState([]);
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
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts`, {}, token);
      if (res.ok) setPosts(await res.json());
    } catch (err) { console.error('Failed to fetch posts'); }
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
      const data = await res.json();
      if (res.ok && data.success) {
        showToast('Automation Loop Completed! 🚀');
        if (data.post) {
          setPosts(prev => [data.post, ...prev]);
        } else {
          fetchPosts(); // fallback refresh
        }
      } else {
        showToast('Automation Failed', true);
      }
    } catch (err) {
      console.error(err);
      showToast('Error running automation', true);
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem', background: 'rgba(255,255,255,0.03)', padding: '1.5rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.75rem' }}>Social Scheduler</h1>
            <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
              Configure AI publishing frequency and monitor automated delivery logs.
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Frequency */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(0,0,0,0.3)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
               <Clock size={16} className="text-muted" />
               <span style={{ fontSize: '0.85rem', fontWeight: '600' }}>Post Every</span>
               <select 
                 value={frequencyHours} 
                 onChange={(e) => handleFrequencyChange(Number(e.target.value))}
                 style={{ background: 'transparent', border: 'none', color: '#fff', outline: 'none', fontSize: '0.9rem', cursor: 'pointer', fontWeight: '700' }}
               >
                 <option value={1}>1 Hour</option>
                 <option value={2}>2 Hours</option>
                 <option value={4}>4 Hours</option>
                 <option value={6}>6 Hours</option>
                 <option value={12}>12 Hours</option>
                 <option value={24}>24 Hours</option>
               </select>
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

        {/* LOGS SECTION */}
        <div className="glass-panel" style={{ overflow: 'hidden', border: '1px solid var(--border-color)', boxShadow: 'none', background: 'rgba(255,255,255,0.02)' }}>
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
              {posts.length === 0 ? (
                <tr>
                  <td colSpan="4" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No posts currently logged. Run the automation loop.
                  </td>
                </tr>
              ) : (
                posts.map(post => (
                  <tr key={post.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '1rem 1.5rem' }}>
                      <span style={{ 
                        fontSize: '0.75rem', fontWeight: '700', padding: '0.3rem 0.7rem', 
                        borderRadius: '30px', 
                        background: post.status === 'POSTED' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)', 
                        color: post.status === 'POSTED' ? 'var(--success)' : '#f59e0b' 
                      }}>
                        {post.status || 'POSTED'}
                      </span>
                    </td>
                    <td style={{ padding: '1rem 1.5rem', fontWeight: '600', fontSize: '0.9rem' }}>
                      {post.platform || 'INSTAGRAM'}
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
                <button onClick={() => setEditingPost(null)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(255,255,255,0.1)', borderRadius: '50%', padding: '0.3rem', marginRight: '1rem' }}>
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
                    style={{ width: '100%', padding: '1rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', color: '#fff', resize: 'vertical', fontSize: '0.9rem', lineHeight: 1.5 }}
                  />
                  <div style={{ textAlign: 'right', fontSize: '0.8rem', color: editCaption.length > 2200 ? 'var(--danger)' : 'var(--text-muted)', marginTop: '-1rem' }}>
                    {editCaption.length} / 2200 characters
                  </div>
                  
                  <div>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: '600' }}>Media (Image/Video)</label>
                    <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem' }}>
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
                  
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', background: 'rgba(255,255,255,0.1)', padding: '0.25rem', borderRadius: '30px' }}>
                     <button style={{ padding: '0.4rem 1rem', background: 'transparent', border: 'none', color: 'var(--text-muted)', fontWeight: '600', cursor: 'pointer' }}>Reels</button>
                     <button style={{ padding: '0.4rem 1rem', background: 'var(--secondary-color)', borderRadius: '20px', border: 'none', color: '#fff', fontWeight: '600', cursor: 'pointer' }}>Feed</button>
                     <button style={{ padding: '0.4rem 1rem', background: 'transparent', border: 'none', color: 'var(--text-muted)', fontWeight: '600', cursor: 'pointer' }}>Profile</button>
                  </div>

                  <div style={{ width: '100%', maxWidth: '350px', background: '#111', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                    {/* Fake Instagram Header */}
                    <div style={{ padding: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                         <span style={{ color: 'var(--secondary-color)', fontWeight: 'bold' }}>Q</span>
                      </div>
                      <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>QuantCAI</span>
                      <div style={{ marginLeft: 'auto', display: 'flex', gap: '3px' }}>
                        <div style={{ width: '4px', height: '4px', background: 'var(--text-muted)', borderRadius: '50%' }}></div>
                        <div style={{ width: '4px', height: '4px', background: 'var(--text-muted)', borderRadius: '50%' }}></div>
                        <div style={{ width: '4px', height: '4px', background: 'var(--text-muted)', borderRadius: '50%' }}></div>
                      </div>
                    </div>

                    {/* Media */}
                    <div style={{ width: '100%', aspectRatio: '1/1', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {editMedia ? (
                        editMedia.includes('video') || editMedia.endsWith('.mp4') ? (
                          <video src={editMedia} style={{ width: '100%', height: '100%', objectFit: 'cover' }} controls />
                        ) : (
                          <img src={editMedia} alt="Preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        )
                      ) : (
                         <div style={{ color: 'var(--text-muted)', textAlign: 'center' }}>
                           <Video size={32} style={{ opacity: 0.5, marginBottom: '0.5rem' }}/>
                           <p style={{ margin: 0, fontSize: '0.8rem' }}>No media attached</p>
                         </div>
                      )}
                    </div>

                    {/* Fake Instagram Footer */}
                    <div style={{ padding: '0.75rem' }}>
                       <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                         <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                         <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                         <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                       </div>
                       <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.4 }}>
                         <span style={{ fontWeight: '600', marginRight: '0.5rem' }}>QuantCAI</span>
                         {editCaption}
                       </p>
                    </div>
                  </div>

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
