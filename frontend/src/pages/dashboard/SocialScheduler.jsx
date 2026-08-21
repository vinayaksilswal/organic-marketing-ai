import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE, authFetch } from '../../config';
import { CheckCircle2, Clock, Play, FileText, X, Image as ImageIcon, Video, Send, Settings, Mail, Users, Edit3, AlertTriangle, RefreshCw, CalendarDays, Sparkles, Plus } from 'lucide-react';
import PostCalendar from '../../components/PostCalendar';

const DAY_LABELS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

const labelSm = {
  display: 'block', fontSize: '0.78rem', fontWeight: 700,
  color: 'var(--text-muted)', marginBottom: '0.4rem',
};

const inputSm = {
  width: '100%', padding: '0.6rem 0.7rem', borderRadius: 10,
  border: '1px solid var(--border-color)', background: 'rgba(11,16,32,0.03)',
  color: 'var(--text-main)', fontSize: '0.88rem', minHeight: 44,
};

const chipStyle = (on) => ({
  minHeight: 40, padding: '0 0.85rem', borderRadius: 10, cursor: 'pointer',
  fontSize: '0.82rem', fontWeight: 600,
  background: on ? 'var(--primary-color)' : 'rgba(11,16,32,0.04)',
  color: on ? '#fff' : 'var(--text-main)',
  border: `1px solid ${on ? 'var(--primary-color)' : 'var(--border-color)'}`,
});

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
  const [publishingMode, setPublishingMode] = useState('PUBLIC'); // 'PUBLIC' | 'PRIVATE' | 'DRAFT_REVIEW'
  const [runningLoop, setRunningLoop] = useState(false);

  // Edit Modal State
  const [editingPost, setEditingPost] = useState(null);
  const [editCaption, setEditCaption] = useState('');
  const [editMedia, setEditMedia] = useState(null);

  // One-Time Media Scheduling State
  const [scheduledPosts, setScheduledPosts] = useState([]);
  const [loadingScheduled, setLoadingScheduled] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [scheduleMediaId, setScheduleMediaId] = useState('');
  const [scheduleMediaUrl, setScheduleMediaUrl] = useState('');
  const [scheduleCaption, setScheduleCaption] = useState('');
  const [schedulePlatform, setSchedulePlatform] = useState('BOTH');
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('18:00');
  const [generatingCaption, setGeneratingCaption] = useState(false);
  const [schedulingPost, setSchedulingPost] = useState(false);

  // Repeat rule. Kept beside the one-time state because it schedules the same
  // asset through the same modal picker -- only the dates differ.

  // Which of the four views is showing.
  const [section, setSection] = useState('calendar');
  const [repeatMode, setRepeatMode] = useState('weekly');   // 'weekly' | 'monthly'
  const [repeatDays, setRepeatDays] = useState([0, 2, 4]);  // Mon, Wed, Fri
  const [repeatDayOfMonth, setRepeatDayOfMonth] = useState(1);
  const [repeatTime, setRepeatTime] = useState('18:00');
  const [repeatCount, setRepeatCount] = useState(8);
  const [repeatMediaId, setRepeatMediaId] = useState('');
  const [savingRepeat, setSavingRepeat] = useState(false);

  const submitRepeat = async () => {
    if (!repeatMediaId) return showToast('Choose an asset to repeat.', true);
    if (repeatMode === 'weekly' && repeatDays.length === 0) {
      return showToast('Pick at least one day of the week.', true);
    }
    setSavingRepeat(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts/schedule-recurring`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          mediaId: repeatMediaId,
          platform: schedulePlatform,
          repeat: repeatMode,
          daysOfWeek: repeatMode === 'weekly' ? repeatDays : null,
          dayOfMonth: repeatMode === 'monthly' ? Number(repeatDayOfMonth) : null,
          timeOfDay: repeatTime,
          occurrences: Number(repeatCount),
        }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Could not schedule that.');
      showToast(data.message || `${data.created} posts scheduled.`);
      setRepeatMediaId('');
      await fetchScheduledPosts();
      await fetchPosts();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSavingRepeat(false);
    }
  };

  useEffect(() => {
    fetchSettings();
    fetchPosts();
    fetchMedia();
    fetchScheduledPosts();
    // The preview shows the real business name and handle rather than a
    // hardcoded "Organiflo", so it reflects what will actually be published.
    (async () => {
      try {
        const res = await authFetch(`${API_BASE}/businesses`, {}, token);
        if (!res.ok) return;
        const all = await res.json();
        if (Array.isArray(all)) {
          const found = all.find(b => b.id === activeWorkspaceId) || all[0] || null;
          setBusiness(found);
          if (found?.publishingMode) setPublishingMode(found.publishingMode);
        }
      } catch { /* preview falls back to a neutral placeholder */ }
    })();
  }, [activeWorkspaceId]);

  const fetchScheduledPosts = async () => {
    setLoadingScheduled(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts/scheduled`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId }
      }, token);
      if (res.ok) setScheduledPosts(await res.json());
    } catch {}
    finally { setLoadingScheduled(false); }
  };

  const openScheduleModal = (mediaItem = null) => {
    if (mediaItem) {
      setScheduleMediaId(mediaItem.id || '');
      setScheduleMediaUrl(mediaItem.url || '');
      setScheduleCaption(mediaItem.caption || '');
    } else if (mediaList.length > 0) {
      setScheduleMediaId(mediaList[0].id || '');
      setScheduleMediaUrl(mediaList[0].url || '');
      setScheduleCaption(mediaList[0].caption || '');
    } else {
      setScheduleMediaId('');
      setScheduleMediaUrl('');
      setScheduleCaption('');
    }
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setScheduleDate(tomorrow.toISOString().split('T')[0]);
    setScheduleTime('18:00');
    setIsScheduleModalOpen(true);
  };

  const handleGenerateMediaCaption = async () => {
    setGeneratingCaption(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts/generate-media-caption`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          mediaId: scheduleMediaId || null,
          mediaUrl: scheduleMediaUrl || null,
          topic: business?.name || 'Brand Spotlight'
        })
      }, token);
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.caption) {
        setScheduleCaption(data.caption);
        showToast('AI caption generated! ✨');
      } else {
        throw new Error(data.detail || 'Could not generate caption');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setGeneratingCaption(false);
    }
  };

  const handleSaveOneTimeSchedule = async () => {
    if (!scheduleMediaUrl && !scheduleMediaId) {
      return showToast('Please select or provide a media asset to schedule', true);
    }
    if (!scheduleDate || !scheduleTime) {
      return showToast('Please select date and time for the scheduled post', true);
    }

    setSchedulingPost(true);
    try {
      const schedDt = new Date(`${scheduleDate}T${scheduleTime}:00`);
      const res = await authFetch(`${API_BASE}/marketing/posts/from-media`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          mediaId: scheduleMediaId || null,
          mediaUrl: scheduleMediaUrl || null,
          customCaption: scheduleCaption,
          platform: schedulePlatform,
          scheduledAt: schedDt.toISOString(),
          isOneTimeSchedule: true,
          status: 'SCHEDULED',
        })
      }, token);

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Failed to schedule post');

      showToast(`Post scheduled for ${scheduleDate} at ${scheduleTime}! 🚀`);
      setIsScheduleModalOpen(false);
      fetchScheduledPosts();
      fetchPosts();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSchedulingPost(false);
    }
  };

  const handleCancelScheduledPost = async (postId) => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/posts/scheduled/${postId}`, {
        method: 'DELETE',
        headers: { 'X-Workspace-Id': activeWorkspaceId }
      }, token);
      if (res.ok) {
        showToast('Scheduled post cancelled.');
        fetchScheduledPosts();
        fetchPosts();
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const handlePublishScheduledNow = async (postId) => {
    try {
      showToast('Publishing scheduled post now...', false);
      const res = await authFetch(`${API_BASE}/marketing/posts/scheduled/${postId}/publish-now`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId }
      }, token);
      if (res.ok) {
        showToast('Post published live! 🚀');
        fetchScheduledPosts();
        fetchPosts();
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/settings`, {}, token);
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          setAutoApproveActive(data.autoApprove);
          setFrequencyHours(data.intervalHours);
          if (data.publishingMode) setPublishingMode(data.publishingMode);
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

  const handlePublishingModeChange = async (mode) => {
    setPublishingMode(mode);
    try {
      await authFetch(`${API_BASE}/marketing/settings/publishing-mode`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({ publishingMode: mode })
      }, token);
      showToast(`Publishing mode updated to: ${mode === 'PUBLIC' ? 'Public (Direct Publish)' : mode === 'PRIVATE' ? 'Private / Unlisted' : 'Hold for review'}`);
    } catch (err) {
      console.error('Failed to update publishing mode', err);
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem', background: 'rgba(11, 16, 32, 0.03)', padding: '1.5rem', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(11,16,32,0.04)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(11,16,32,0.04)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <label style={{ position: 'relative', display: 'inline-block', width: '40px', height: '22px' }}>
                 <input type="checkbox" checked={autoApproveActive} onChange={(e) => handleAutoApproveChange(e.target.checked)} style={{ opacity: 0, width: 0, height: 0 }} />
                <span style={{ position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: autoApproveActive ? 'var(--success)' : 'rgba(255,255,255,0.2)', transition: '.4s', borderRadius: '34px' }}>
                  <span style={{ position: 'absolute', content: '""', height: '14px', width: '14px', left: autoApproveActive ? '22px' : '4px', bottom: '4px', backgroundColor: 'white', transition: '.4s', borderRadius: '50%' }}></span>
                </span>
              </label>
              <span style={{ fontSize: '0.85rem', fontWeight: '600' }}>Auto-Approve</span>
            </div>

            {/* Publishing Visibility Mode Control */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(11,16,32,0.04)', padding: '0.35rem 0.6rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 700 }}>Mode:</span>
              <button
                type="button"
                onClick={() => handlePublishingModeChange('PUBLIC')}
                style={{
                  background: publishingMode === 'PUBLIC' ? 'rgba(16,185,129,0.2)' : 'transparent',
                  color: publishingMode === 'PUBLIC' ? '#10b981' : 'var(--text-muted)',
                  border: publishingMode === 'PUBLIC' ? '1px solid #10b981' : '1px solid transparent',
                  padding: '0.25rem 0.5rem',
                  borderRadius: 8,
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🌐 Public
              </button>
              <button
                type="button"
                onClick={() => handlePublishingModeChange('PRIVATE')}
                style={{
                  background: publishingMode === 'PRIVATE' ? 'rgba(245,158,11,0.2)' : 'transparent',
                  color: publishingMode === 'PRIVATE' ? '#f59e0b' : 'var(--text-muted)',
                  border: publishingMode === 'PRIVATE' ? '1px solid #f59e0b' : '1px solid transparent',
                  padding: '0.25rem 0.5rem',
                  borderRadius: 8,
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🔒 Private
              </button>
              <button
                type="button"
                onClick={() => handlePublishingModeChange('DRAFT_REVIEW')}
                style={{
                  background: publishingMode === 'DRAFT_REVIEW' ? 'rgba(59,130,246,0.2)' : 'transparent',
                  color: publishingMode === 'DRAFT_REVIEW' ? '#60a5fa' : 'var(--text-muted)',
                  border: publishingMode === 'DRAFT_REVIEW' ? '1px solid #3b82f6' : '1px solid transparent',
                  padding: '0.25rem 0.5rem',
                  borderRadius: 8,
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                📝 Review Queue
              </button>
            </div>

            {/* Run Manually button. It is a manual trigger for the same cycle the
                scheduler runs on its own, and calling it "Run Automation" read as
                if it switched the automation on -- so people pressed it to enable
                something and got one immediate post instead. */}
            <button 
              className="btn btn-primary" 
              onClick={handleRunAutomation}
              disabled={runningLoop}
              style={{ background: '#3b82f6', color: '#fff', fontWeight: '600', padding: '0.6rem 1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              {runningLoop ? <span className="spinner"></span> : <>⚡ Run Manually</>}
            </button>
          </div>
        </div>

        {/* One page, four jobs. Stacked end to end they made a single
            column three screens tall, where finding the repeat rule meant
            scrolling past the whole delivery log. Each is now its own view,
            and the tab says how much is waiting inside it. */}
        <div style={{
          display: 'flex', gap: '0.35rem', marginBottom: '1.5rem', flexWrap: 'wrap',
          borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem',
        }}>
          {[
            { key: 'calendar', label: 'Calendar', icon: <CalendarDays size={15} />,
              hint: 'Everything on the day it goes out' },
            { key: 'once', label: 'One-time posts', icon: <Clock size={15} />,
              count: scheduledPosts.length, hint: 'Schedule a single post for a date and time' },
            { key: 'repeat', label: 'Repeating', icon: <RefreshCw size={15} />,
              hint: 'Days of the week, or a date each month' },
            { key: 'log', label: 'Delivery log', icon: null,
              count: posts.length, hint: 'What was published, and why anything failed' },
          ].map((t) => {
            const active = section === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setSection(t.key)}
                title={t.hint}
                aria-current={active ? 'page' : undefined}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.45rem',
                  padding: '0.55rem 0.95rem', borderRadius: 10, cursor: 'pointer',
                  fontSize: '0.88rem', fontWeight: active ? 700 : 500,
                  border: '1px solid ' + (active ? 'var(--primary-color)' : 'transparent'),
                  background: active ? 'rgba(99,102,241,0.10)' : 'transparent',
                  color: active ? 'var(--primary-color)' : 'var(--text-muted)',
                  transition: 'background .15s ease, color .15s ease',
                }}
              >
                {t.icon}
                {t.label}
                {typeof t.count === 'number' && t.count > 0 && (
                  <span style={{
                    fontSize: '0.72rem', fontWeight: 700, padding: '0.05rem 0.4rem',
                    borderRadius: 999, background: active ? 'var(--primary-color)' : 'var(--border-color)',
                    color: active ? '#fff' : 'var(--text-muted)',
                  }}>{t.count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* SCHEDULE — the month, with every post on the day it went out.
            A table answers "what happened last?"; the questions people
            actually have about a schedule are shape questions: is anything
            going out tomorrow, did Tuesday publish, why is there a gap. */}
        {section === 'calendar' && (
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
        )}

        {/* ONE-TIME SCHEDULED POSTS SECTION */}
        {section === 'once' && (
        <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem', border: '1px solid rgba(249, 115, 22, 0.25)', background: 'rgba(249, 115, 22, 0.02)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Clock size={18} color="#f97316" />
              <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)', fontWeight: 800 }}>
                One-Time Scheduled Releases ({scheduledPosts.length})
              </h2>
              <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.55rem', borderRadius: 10, background: 'rgba(249,115,22,0.15)', color: '#f97316', fontWeight: 700 }}>
                Publishes at exact set date/time
              </span>
            </div>

            <button
              onClick={() => openScheduleModal()}
              style={{
                background: 'rgba(249,115,22,0.15)',
                color: '#f97316',
                border: '1px solid rgba(249,115,22,0.4)',
                borderRadius: 8,
                padding: '0.4rem 0.85rem',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <Plus size={14} /> Schedule Post from Media
            </button>
          </div>

          {loadingScheduled ? (
            <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
              <span className="spinner" style={{ width: 16, height: 16, marginRight: 8 }} /> Loading scheduled releases...
            </div>
          ) : scheduledPosts.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem 1rem', background: 'rgba(11, 16, 32, 0.02)', borderRadius: 10, border: '1px dashed rgba(255,255,255,0.1)' }}>
              <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'rgba(249,115,22,0.1)', color: '#f97316', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem' }}>
                <Clock size={22} />
              </div>
              <h4 style={{ margin: '0 0 0.3rem', fontSize: '0.95rem' }}>No One-Time Posts Scheduled</h4>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', maxWidth: 460, margin: '0 auto 1rem' }}>
                Want to post a specific video or image on an exact day and time? Pick any creative from your Media Catalog to schedule a one-time release.
              </p>
              <button
                className="btn btn-primary"
                onClick={() => openScheduleModal()}
                style={{ background: '#f97316', border: 'none', fontSize: '0.82rem', fontWeight: 700, padding: '0.5rem 1.1rem' }}
              >
                + Pick Media &amp; Set Time
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
              {scheduledPosts.map(p => {
                const schedDate = p.scheduledAt ? new Date(p.scheduledAt) : null;
                const dateFormatted = schedDate ? schedDate.toLocaleString(undefined, {
                  weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true
                }) : 'Pending';
                const mediaUrl = p.mediaUrls?.[0] || '';
                const isVideo = mediaUrl && (mediaUrl.endsWith('.mp4') || mediaUrl.includes('/video/'));

                return (
                  <div key={p.id} style={{
                    background: 'rgba(11,16,32,0.04)',
                    borderRadius: 10,
                    border: '1px solid rgba(249,115,22,0.25)',
                    padding: '1rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '0.75rem',
                  }}>
                    <div style={{ display: 'flex', gap: '0.85rem' }}>
                      {mediaUrl ? (
                        <div style={{ width: 68, height: 68, borderRadius: 8, overflow: 'hidden', background: '#000', flexShrink: 0, border: '1px solid var(--border-color)', position: 'relative' }}>
                          {isVideo ? (
                            <>
                              <video src={mediaUrl} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                              <div style={{ position: 'absolute', bottom: 2, right: 2, background: 'rgba(11,16,32,0.04)', borderRadius: 4, padding: '1px 3px' }}>
                                <Video size={10} color="#fff" />
                              </div>
                            </>
                          ) : (
                            <img src={mediaUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          )}
                        </div>
                      ) : (
                        <div style={{ width: 68, height: 68, borderRadius: 8, background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                          <ImageIcon size={24} color="var(--text-muted)" />
                        </div>
                      )}

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
                          <span style={{ fontSize: '0.68rem', fontWeight: 800, padding: '0.1rem 0.45rem', borderRadius: 4, background: '#f97316', color: '#fff' }}>
                            {p.platform || 'BOTH'}
                          </span>
                          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                            Scheduled
                          </span>
                        </div>
                        <div style={{ fontSize: '0.84rem', fontWeight: 800, color: '#fcd34d', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Clock size={12} /> {dateFormatted}
                        </div>
                        <p style={{ margin: '0.3rem 0 0', fontSize: '0.76rem', color: 'var(--text-main)', lineHeight: 1.35, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                          {p.caption || 'No caption provided'}
                        </p>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '0.65rem' }}>
                      <button
                        onClick={() => handleCancelScheduledPost(p.id)}
                        style={{ background: 'none', border: 'none', color: '#f87171', fontSize: '0.76rem', fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handlePublishScheduledNow(p.id)}
                        style={{
                          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 8,
                          padding: '0.3rem 0.75rem',
                          fontSize: '0.76rem',
                          fontWeight: 800,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.3rem'
                        }}
                      >
                        <Send size={12} /> Publish Now
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        )}

        {/* REPEAT A POST.
            Its own section rather than a mode inside the one-time dialog: a
            date and a rule are different decisions, and folding them into one
            form makes both harder to read. Occurrences are materialised as
            ordinary scheduled posts, so everything below on this page already
            knows how to show and cancel them. */}
        {section === 'repeat' && (
        <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
            <RefreshCw size={18} color="var(--primary-color)" />
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Repeat a post</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Certain weekdays, or a day of the month
            </span>
          </div>

          <div style={{ display: 'grid', gap: '1.1rem' }}>
              <div>
                <label style={labelSm}>Asset</label>
                <select value={repeatMediaId} onChange={e => setRepeatMediaId(e.target.value)} style={inputSm}>
                  <option value="">Choose from your media…</option>
                  {mediaList.map(m => (
                    <option key={m.id} value={m.id}>
                      {(m.caption || m.filename || 'Untitled').slice(0, 70)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={labelSm}>Repeats</label>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {[['weekly', 'Certain weekdays'], ['monthly', 'A day each month']].map(([k, lbl]) => (
                    <button key={k} type="button" onClick={() => setRepeatMode(k)}
                            style={chipStyle(repeatMode === k)}>{lbl}</button>
                  ))}
                </div>
              </div>

              {repeatMode === 'weekly' ? (
                <div>
                  <label style={labelSm}>On these days</label>
                  <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                    {DAY_LABELS.map((d, i) => (
                      <button key={d} type="button"
                              onClick={() => setRepeatDays(prev => prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i].sort())}
                              style={{ ...chipStyle(repeatDays.includes(i)), minWidth: 52 }}>{d}</button>
                    ))}
                  </div>
                </div>
              ) : (
                <div>
                  <label style={labelSm}>Day of the month</label>
                  <select value={repeatDayOfMonth} onChange={e => setRepeatDayOfMonth(e.target.value)} style={{ ...inputSm, maxWidth: 200 }}>
                    {Array.from({ length: 28 }, (_, i) => i + 1).map(d => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                  <small style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    Stops at 28 — later dates do not exist in every month, and quietly moving a post is worse than not offering it.
                  </small>
                </div>
              )}

              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 150px' }}>
                  <label style={labelSm}>Time</label>
                  <input type="time" value={repeatTime} onChange={e => setRepeatTime(e.target.value)} style={inputSm} />
                </div>
                <div style={{ flex: '1 1 150px' }}>
                  <label style={labelSm}>How many</label>
                  <select value={repeatCount} onChange={e => setRepeatCount(e.target.value)} style={inputSm}>
                    {[4, 8, 12, 20, 31].map(n => <option key={n} value={n}>{n} posts</option>)}
                  </select>
                </div>
              </div>

              <div>
                <button onClick={submitRepeat} disabled={savingRepeat} className="btn btn-primary"
                        style={{ minHeight: 44, fontWeight: 700 }}>
                  {savingRepeat ? 'Scheduling…' : 'Schedule the repeats'}
                </button>
                <small style={{ display: 'block', marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  These appear above as normal scheduled posts, so you can cancel any single one.
                </small>
              </div>
          </div>
        </div>
        )}

        {/* LOGS SECTION */}
        {section === 'log' && (
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
                          borderRadius: 8, background: 'rgba(239,68,68,0.07)',
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
                      {/* Every platform that actually carried this post. It
                          used to read Facebook and Instagram only, so a post
                          delivered to X and LinkedIn showed nothing at all and
                          looked like it had gone nowhere. */}
                      {[
                        post.fbPostId && 'FB',
                        post.igPostId && 'IG',
                        post.twitterPostId && 'X',
                        post.linkedinPostId && 'LinkedIn',
                      ].filter(Boolean).length > 0 && (
                        <div style={{ marginTop: '0.3rem', fontSize: '0.68rem', fontWeight: 500, color: 'var(--text-muted)' }}>
                          {[
                            post.fbPostId && 'FB',
                            post.igPostId && 'IG',
                            post.twitterPostId && 'X',
                            post.linkedinPostId && 'LinkedIn',
                          ].filter(Boolean).map((name) => `${name} ✓`).join('  ')}
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
        )}

        {/* SIDE-BY-SIDE EDIT MODAL */}
        {editingPost && (
          <div className="modal-overlay" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
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
                              showToast('Tip: For best results on Reels, use 9:16 aspect ratio (1080x1920)', false);
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
                <div style={{ flex: 1, padding: '1.5rem', background: 'rgba(11,16,32,0.04)', overflowY: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  
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
                                padding: '0.4rem 1.1rem', borderRadius: '16px', border: 'none', cursor: 'pointer',
                                fontWeight: 600, fontSize: '0.85rem',
                                background: previewTab === k ? 'var(--secondary-color)' : 'transparent',
                                color: previewTab === k ? 'var(--text-main)' : 'var(--text-muted)',
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
                          <div className="keep-cols" style={{ width: '100%', maxWidth: 330, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 3 }}>
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
                          <div style={{ width: '100%', maxWidth: 350, background: '#111', color: '#fff', borderRadius: 10, border: '1px solid var(--border-color)', overflow: 'hidden' }}>
                            <div style={{ padding: '0.7rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                              <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg,var(--primary-color),var(--secondary-color))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.8rem' }}>
                                {(business?.name || 'B').charAt(0).toUpperCase()}
                              </div>
                              <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{handle}</span>
                              <div style={{ marginLeft: 'auto', display: 'flex', gap: 3 }}>
                                {[0, 1, 2].map(i => <div key={i} style={{ width: 3.5, height: 3.5, background: 'rgba(255,255,255,0.65)', borderRadius: '50%' }} />)}
                              </div>
                            </div>

                            <div style={{ width: '100%', aspectRatio: ratio, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              {mediaEl}
                            </div>

                            <div style={{ padding: '0.7rem 0.75rem' }}>
                              <div style={{ display: 'flex', gap: '0.9rem', marginBottom: '0.5rem', color: '#fff' }}>
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

        {/* ONE-TIME MEDIA SCHEDULE MODAL */}
        {isScheduleModalOpen && (
          <div className="modal-overlay" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.82)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1200, padding: '1rem' }}
            onClick={e => { if (e.target === e.currentTarget) setIsScheduleModalOpen(false); }}>
            <div className="glass-panel keep-pad" style={{ width: '100%', maxWidth: 720, maxHeight: '90vh', overflow: 'auto', padding: '1.75rem', background: 'rgba(11,16,32,0.03)', border: '1px solid rgba(249,115,22,0.35)', borderRadius: 14, boxShadow: '0 20px 40px rgba(0,0,0,0.7)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <div style={{ width: 36, height: 36, borderRadius: 8, background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 10px rgba(249,115,22,0.3)' }}>
                    <Clock size={20} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)' }}>Schedule Post from Media</h3>
                    <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>Pick an asset from your library, set the exact date &amp; time, and Organiflo will publish it automatically.</p>
                  </div>
                </div>
                <button onClick={() => setIsScheduleModalOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer' }}><X size={20} /></button>
              </div>

              {/* STEP 1: SELECT MEDIA FROM CATALOG */}
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.4rem' }}>
                  1. Select Media Creative from Library
                </label>
                {mediaList.length === 0 ? (
                  <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px dashed rgba(255,255,255,0.1)', textAlign: 'center' }}>
                    <p style={{ margin: '0 0 0.5rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>No media in library yet. Paste a direct image/video URL below:</p>
                    <input
                      type="url"
                      placeholder="https://.../video.mp4 or image.jpg"
                      value={scheduleMediaUrl}
                      onChange={e => setScheduleMediaUrl(e.target.value)}
                      style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: 8, background: '#000', border: '1px solid var(--border-color)', color: '#fff', fontSize: '0.85rem' }}
                    />
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: '0.5rem', maxHeight: 180, overflowY: 'auto', padding: '0.5rem', background: 'rgba(11,16,32,0.03)', borderRadius: 10, border: '1px solid var(--border-color)' }}>
                      {mediaList.map(m => {
                        const isSel = scheduleMediaId === m.id || scheduleMediaUrl === m.url;
                        const isVid = m.url && (m.url.endsWith('.mp4') || m.url.includes('/video/'));
                        return (
                          <div
                            key={m.id}
                            onClick={() => {
                              setScheduleMediaId(m.id);
                              setScheduleMediaUrl(m.url);
                              if (m.caption && !scheduleCaption) setScheduleCaption(m.caption);
                            }}
                            style={{
                              aspectRatio: '1/1',
                              borderRadius: 8,
                              overflow: 'hidden',
                              border: isSel ? '2px solid #f97316' : '1px solid var(--border-color)',
                              cursor: 'pointer',
                              position: 'relative',
                              background: '#000',
                              boxShadow: isSel ? '0 0 10px rgba(249,115,22,0.4)' : 'none',
                            }}
                          >
                            {isVid ? (
                              <video src={m.url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (
                              <img src={m.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            )}
                            {isVid && (
                              <div style={{ position: 'absolute', top: 3, right: 3, background: 'rgba(11,16,32,0.04)', borderRadius: 4, padding: '1px 3px' }}>
                                <Video size={10} color="#fff" />
                              </div>
                            )}
                            {isSel && (
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(249,115,22,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <CheckCircle2 size={20} color="#fff" />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {/* URL Fallback */}
                    <div style={{ marginTop: '0.4rem' }}>
                      <input
                        type="url"
                        placeholder="Or paste custom media URL..."
                        value={scheduleMediaUrl}
                        onChange={e => { setScheduleMediaUrl(e.target.value); setScheduleMediaId(''); }}
                        style={{ width: '100%', padding: '0.45rem 0.75rem', borderRadius: 8, background: 'rgba(11,16,32,0.03)', border: '1px solid var(--border-color)', color: 'var(--text-main)', fontSize: '0.78rem' }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* STEP 2: CAPTION & AI WRITER */}
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)' }}>
                    2. Post Caption &amp; Hashtags
                  </label>
                  <button
                    type="button"
                    onClick={handleGenerateMediaCaption}
                    disabled={generatingCaption}
                    style={{
                      background: 'rgba(249,115,22,0.15)',
                      border: '1px solid rgba(249,115,22,0.4)',
                      color: '#f97316',
                      borderRadius: 8,
                      padding: '0.2rem 0.6rem',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.3rem'
                    }}
                  >
                    {generatingCaption ? <RefreshCw className="spin" size={12} /> : <Sparkles size={12} />}
                    {generatingCaption ? 'Writing...' : '✨ Write AI Caption'}
                  </button>
                </div>
                <textarea
                  rows={4}
                  value={scheduleCaption}
                  onChange={e => setScheduleCaption(e.target.value)}
                  placeholder="Write engaging caption with hook, value, and #hashtags..."
                  style={{
                    width: '100%',
                    padding: '0.7rem',
                    borderRadius: 8,
                    background: 'rgba(11,16,32,0.03)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-main)',
                    fontSize: '0.85rem',
                    lineHeight: 1.45,
                    resize: 'vertical'
                  }}
                />
              </div>

              {/* STEP 3: TARGET PLATFORMS & DATE/TIME */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.4rem' }}>
                    3. Target Platform
                  </label>
                  <select
                    value={schedulePlatform}
                    onChange={e => setSchedulePlatform(e.target.value)}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: 8, background: 'rgba(11,16,32,0.03)', border: '1px solid var(--border-color)', color: 'var(--text-main)', fontSize: '0.85rem', appearance: 'auto' }}
                  >
                    <option value="BOTH">Instagram &amp; Facebook (Both)</option>
                    <option value="INSTAGRAM">Instagram Only (Reels / Feed)</option>
                    <option value="FACEBOOK">Facebook Page Only</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.4rem' }}>
                    4. Pick Date &amp; Time
                  </label>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <input
                      type="date"
                      value={scheduleDate}
                      onChange={e => setScheduleDate(e.target.value)}
                      style={{ flex: 1, padding: '0.55rem', borderRadius: 8, background: 'rgba(11,16,32,0.03)', border: '1px solid var(--border-color)', color: 'var(--text-main)', fontSize: '0.85rem' }}
                    />
                    <input
                      type="time"
                      value={scheduleTime}
                      onChange={e => setScheduleTime(e.target.value)}
                      style={{ width: 110, padding: '0.55rem', borderRadius: 8, background: 'rgba(11,16,32,0.03)', border: '1px solid var(--border-color)', color: 'var(--text-main)', fontSize: '0.85rem' }}
                    />
                  </div>
                </div>
              </div>

              {/* QUICK DATE SHORTCUT PRESETS */}
              <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Quick Times:</span>
                {[
                  { label: 'Today 6 PM', getDt: () => { const d = new Date(); return { date: d.toISOString().split('T')[0], time: '18:00' }; } },
                  { label: 'Tomorrow 12 PM', getDt: () => { const d = new Date(); d.setDate(d.getDate() + 1); return { date: d.toISOString().split('T')[0], time: '12:00' }; } },
                  { label: 'Tomorrow 6 PM', getDt: () => { const d = new Date(); d.setDate(d.getDate() + 1); return { date: d.toISOString().split('T')[0], time: '18:00' }; } },
                  { label: 'In 2 Days (Peak)', getDt: () => { const d = new Date(); d.setDate(d.getDate() + 2); return { date: d.toISOString().split('T')[0], time: '19:00' }; } },
                ].map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      const res = preset.getDt();
                      setScheduleDate(res.date);
                      setScheduleTime(res.time);
                    }}
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-main)',
                      borderRadius: 8,
                      padding: '0.2rem 0.55rem',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
                <button className="btn btn-secondary" onClick={() => setIsScheduleModalOpen(false)} disabled={schedulingPost}>
                  Cancel
                </button>
                <button
                  onClick={handleSaveOneTimeSchedule}
                  disabled={schedulingPost}
                  className="btn btn-primary"
                  style={{
                    background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
                    border: 'none',
                    fontWeight: 800,
                    padding: '0.65rem 1.4rem',
                    borderRadius: 8,
                    fontSize: '0.88rem',
                    boxShadow: '0 4px 14px rgba(249,115,22,0.35)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    cursor: 'pointer',
                  }}
                >
                  {schedulingPost ? <RefreshCw className="spin" size={15} /> : <Clock size={15} />}
                  {schedulingPost ? 'Scheduling Post...' : 'Schedule One-Time Post 🚀'}
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
