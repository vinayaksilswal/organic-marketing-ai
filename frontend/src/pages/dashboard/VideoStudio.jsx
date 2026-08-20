import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE, authFetch } from '../../config';
import {
  Sparkles, Film, Copy, Check, Wand2, Package, Building2,
  AlertTriangle, Settings, Video, Image as ImageIcon,
  Upload, Trash2, RefreshCw, Clock, Send, Flame, Zap,
  Layers, Volume2, Calendar, Radio, CheckCircle2, ArrowRight,
  TrendingUp, Shield, BarChart3, HelpCircle
} from 'lucide-react';
import ViralValidator from '../../components/ViralValidator';
import PostShipStudio from '../../components/PostShipStudio';

const FACELESS_TOPIC_PRESETS = [
  { id: 'scary_stories', title: 'Scary Stories', tagline: 'Chilling urban legends & paranormal mysteries', icon: '👻', badge: 'VIRAL SUSPENSE' },
  { id: 'jokes', title: 'Jokes & Comedy', tagline: 'Hilarious stand-up & relatable everyday humor', icon: '😂', badge: 'HIGH ENGAGEMENT' },
  { id: 'life_pro_tips', title: 'Life Pro Tips', tagline: 'Psychology hacks & unfair life advantages', icon: '💡', badge: 'HIGH SAVES' },
  { id: 'today_i_learned', title: 'Today I Learned', tagline: 'Mind-blowing historical & real-world facts', icon: '🧠', badge: 'HIGH SHARES' },
  { id: 'you_should_know', title: 'You Should Know', tagline: 'Crucial safety advice & hidden life secrets', icon: '⚠️', badge: 'MUST WATCH' },
  { id: 'custom', title: 'Custom Topic', tagline: 'Write your own custom niche or storyline', icon: '✍️', badge: 'FULL CONTROL' },
];

const VISUAL_STYLE_PRESETS = [
  { id: 'cinematic_realism', name: 'Cinematic Realism', icon: '🎬', desc: '8K Photorealistic 35mm film, moody lighting' },
  { id: 'dark_cyberpunk', name: 'Cyberpunk Anime', icon: '🎨', desc: 'Neon reflections, cel-shaded anime aesthetic' },
  { id: 'retro_comic', name: 'Retro Comic', icon: '🕹️', desc: 'Vintage halftone dots, bold ink action lines' },
  { id: 'vintage_film', name: 'Vintage 35mm', icon: '📸', desc: 'Warm analog grain, kodachrome film stock' },
  { id: 'gameplay_motion', name: '3D Gaming Motion', icon: '🎮', desc: 'Unreal Engine 5 hyper-smooth 3D backdrop' },
  { id: 'pixar_claymation', name: 'Minimal 3D Pixar', icon: '🪄', desc: 'Whimsical 3D character, soft bounce light' },
];

const VOICE_PERSONA_PRESETS = [
  { id: 'adam_storyteller', name: 'Adam', tone: 'Deep Storyteller & Mystery Narrator', gender: 'Male', speed: '0.95x' },
  { id: 'rachel_viral', name: 'Rachel', tone: 'Energetic & Engaging Viral Host', gender: 'Female', speed: '1.10x' },
  { id: 'marcus_authority', name: 'Marcus', tone: 'Sophisticated & Authoritative Guide', gender: 'Male', speed: '1.00x' },
  { id: 'bella_relatable', name: 'Bella', tone: 'Warm & Friendly Conversationalist', gender: 'Female', speed: '1.05x' },
  { id: 'shadow_whisper', name: 'Shadow Whisper', tone: 'Chilling Suspense & Mystery Voice', gender: 'Atmospheric', speed: '0.90x' },
];

const SCHEDULE_PRESETS = [
  { id: 'daily', label: 'Once a Day (Daily)', desc: '1 Short every day at 6:00 PM peak engagement', days: [0,1,2,3,4,5,6] },
  { id: 'three_times_week', label: '3x a Week (Mon/Wed/Fri)', desc: 'Consistent cadence on Mon, Wed, Fri', days: [0,2,4] },
  { id: 'growth_blast', label: 'Twice a Day (Growth Blast)', desc: '2 Shorts/day at 12 PM and 7 PM', days: [0,1,2,3,4,5,6] },
  { id: 'custom', label: 'Custom Days', desc: 'Choose your own active posting days', days: [0,1,2,3,4,5,6] },
];

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  // Main Studio Mode: 'faceless' | 'validator' | 'brand'
  const [studioTab, setStudioTab] = useState('faceless');

  // Faceless Shorts State
  const [selectedTopic, setSelectedTopic] = useState('scary_stories');
  const [customTopicText, setCustomTopicText] = useState('');
  const [selectedStyle, setSelectedStyle] = useState('cinematic_realism');
  const [selectedVoice, setSelectedVoice] = useState('adam_storyteller');
  const [facelessDuration, setFacelessDuration] = useState(20);
  const [schedulePreset, setSchedulePreset] = useState('daily');
  const [publishingMode, setPublishingMode] = useState('PUBLIC'); // 'PUBLIC' | 'PRIVATE' | 'DRAFT_REVIEW'
  const [generatingFaceless, setGeneratingFaceless] = useState(false);
  const [facelessPackage, setFacelessPackage] = useState(null);
  const [activatingAutopilot, setActivatingAutopilot] = useState(false);
  const [autopilotActive, setAutopilotActive] = useState(false);

  // Brand/Product Studio State
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState('');
  const [business, setBusiness] = useState(null);
  const [videoKeySet, setVideoKeySet] = useState(false);
  const [duration, setDuration] = useState(10);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const fileInputRef = React.useRef(null);

  // Video API Config State
  const [showVideoConfig, setShowVideoConfig] = useState(false);
  const [videoProvider, setVideoProvider] = useState('json2video');
  const [videoKey, setVideoKey] = useState('');
  const [videoEndpoint, setVideoEndpoint] = useState('');
  const [savingVideoConfig, setSavingVideoConfig] = useState(false);

  // History State
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historyError, setHistoryError] = useState(null);
  const [attachingId, setAttachingId] = useState(null);
  const [attachTargetId, setAttachTargetId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const attachInputRef = React.useRef(null);

  const fetchHistory = useCallback(async () => {
    if (!activeWorkspaceId) return;
    setLoadingHistory(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (!res.ok) {
        setHistoryError(`Could not load your prompts (error ${res.status}).`);
        return;
      }
      const all = await res.json();
      const rows = (Array.isArray(all) ? all : []).filter(
        m => m.promptType === 'video' || m.prompt || m.generationStatus || m.meta?.faceless_package
      );
      setHistory(rows);
      setHistoryError(null);
      return rows;
    } catch {
      setHistoryError('Could not reach the server to load your prompts.');
    } finally {
      setLoadingHistory(false);
    }
  }, [activeWorkspaceId, token]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Load business & video config
  useEffect(() => {
    if (!activeWorkspaceId) return;
    (async () => {
      try {
        const res = await authFetch(`${API_BASE}/businesses`, {}, token);
        if (res.ok) {
          const all = await res.json();
          if (Array.isArray(all)) {
            const found = all.find(b => b.id === activeWorkspaceId) || all[0] || null;
            setBusiness(found);
            if (found?.publishingMode) setPublishingMode(found.publishingMode);
            if (found?.businessModel === 'Faceless Channel') setAutopilotActive(true);
          }
        }
      } catch {}

      try {
        const res = await authFetch(`${API_BASE}/marketing/products`, {
          headers: { 'X-Workspace-Id': activeWorkspaceId },
        }, token);
        if (res.ok) {
          const d = await res.json();
          setProducts(Array.isArray(d) ? d : []);
        }
      } catch {}
    })();
  }, [activeWorkspaceId, token]);

  // 1-Click Generate Faceless Short
  const handleGenerateFaceless = async () => {
    if (!activeWorkspaceId) return showToast('Select a channel workspace first.', true);
    setGeneratingFaceless(true);
    setFacelessPackage(null);

    try {
      const res = await authFetch(`${API_BASE}/creatives/faceless-generate`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          topic_id: selectedTopic,
          custom_topic: selectedTopic === 'custom' ? customTopicText : null,
          visual_style_id: selectedStyle,
          voice_id: selectedVoice,
          duration_seconds: facelessDuration,
          publishing_mode: publishingMode,
          channel_name: business?.name || 'Faceless Viral Shorts',
          schedule_to_queue: false,
        }),
      }, token);

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Generation failed');

      setFacelessPackage(data.package);
      showToast('Faceless Short Generated Successfully! 🚀');
      await fetchHistory();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setGeneratingFaceless(false);
    }
  };

  // 1-Click Activate Auto-Pilot Schedule
  const handleActivateAutopilot = async () => {
    if (!activeWorkspaceId) return showToast('Select a channel workspace first.', true);
    setActivatingAutopilot(true);
    try {
      const res = await authFetch(`${API_BASE}/creatives/faceless-autopilot`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          schedule_preset: schedulePreset,
          publishing_mode: publishingMode,
          auto_approve: true,
        }),
      }, token);

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Could not activate Auto-Pilot');

      setAutopilotActive(true);
      showToast('🚀 Auto-Pilot Activated! We write, voice, caption & post on your schedule.');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setActivatingAutopilot(false);
    }
  };

  // Brand prompt generation
  const generateBrandPrompt = async () => {
    if (!activeWorkspaceId) return showToast('Select a business first.', true);
    setGenerating(true);
    setResult(null);
    try {
      const res = await authFetch(`${API_BASE}/creatives/auto-video`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({ product_id: productId || null, goal: 'conversion', duration_seconds: duration }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Generation failed');

      setResult(data);
      showToast(data.message || 'Writing your prompt — it will appear below shortly.');
      await fetchHistory();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setGenerating(false);
    }
  };

  const card = { background: '#121217', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: 14, padding: '1.25rem' };

  return (
    <div className="view">
      <div className="container" style={{ padding: '2.5rem 0', maxWidth: 960 }}>
        {/* Main Header */}
        <div style={{ marginBottom: '1.5rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.85rem', display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 900, color: '#fff' }}>
              <Film color="#f97316" size={28} /> AI Video &amp; Shorts Studio
            </h1>
            <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.88rem' }}>
              Faceless Shorts on Auto-Pilot, Algorithmic View Prediction &amp; Brand Video Generation.
            </p>
          </div>

          {/* 3-Tab Studio Switcher */}
          <div style={{
            display: 'inline-flex',
            background: '#181820',
            padding: '0.25rem',
            borderRadius: 12,
            border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <button
              onClick={() => setStudioTab('faceless')}
              style={{
                background: studioTab === 'faceless' ? 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)' : 'none',
                color: studioTab === 'faceless' ? '#fff' : '#a1a1aa',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: 8,
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                transition: 'all 0.2s ease',
              }}
            >
              <Zap size={14} /> Faceless Auto-Pilot
            </button>
            <button
              onClick={() => setStudioTab('validator')}
              style={{
                background: studioTab === 'validator' ? 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)' : 'none',
                color: studioTab === 'validator' ? '#fff' : '#a1a1aa',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: 8,
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                transition: 'all 0.2s ease',
              }}
            >
              <Flame size={14} /> Viral Validator
            </button>
            <button
              onClick={() => setStudioTab('postship')}
              style={{
                background: studioTab === 'postship' ? 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' : 'none',
                color: studioTab === 'postship' ? '#fff' : '#a1a1aa',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: 8,
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                transition: 'all 0.2s ease',
              }}
            >
              <Send size={14} /> PostShip (X, LI, Reddit)
            </button>
            <button
              onClick={() => setStudioTab('brand')}
              style={{
                background: studioTab === 'brand' ? 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)' : 'none',
                color: studioTab === 'brand' ? '#fff' : '#a1a1aa',
                border: 'none',
                padding: '0.5rem 1rem',
                borderRadius: 8,
                fontSize: '0.82rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                transition: 'all 0.2s ease',
              }}
            >
              <Building2 size={14} /> Brand Ads
            </button>
          </div>
        </div>

        {!activeWorkspaceId ? (
          <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', background: '#121217', borderRadius: 16 }}>
            <Building2 size={32} color="#f97316" style={{ marginBottom: '0.9rem' }} />
            <p style={{ margin: 0, color: 'var(--text-muted)' }}>
              Select a channel or business from the sidebar to launch video automation.
            </p>
          </div>
        ) : (
          <>
            {/* ========================================================================= */}
            {/* TAB 1: FACELESS SHORTS ON AUTO-PILOT */}
            {/* ========================================================================= */}
            {studioTab === 'faceless' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {/* Hero Header Card */}
                <div style={{
                  background: 'linear-gradient(135deg, rgba(249,115,22,0.12) 0%, rgba(234,88,12,0.02) 100%)',
                  border: '1px solid rgba(249,115,22,0.3)',
                  borderRadius: 16,
                  padding: '1.35rem 1.5rem',
                }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
                    <div>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.2rem 0.6rem', borderRadius: 20, background: 'rgba(249,115,22,0.15)', border: '1px solid rgba(249,115,22,0.3)', marginBottom: '0.35rem' }}>
                        <Zap size={12} color="#f97316" />
                        <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', color: '#f97316', letterSpacing: '.06em' }}>
                          Faceless Short Videos on Auto-Pilot
                        </span>
                      </div>
                      <h2 style={{ fontSize: '1.35rem', fontWeight: 900, margin: 0, color: '#fff' }}>
                        Pick a topic, pick a voice, pick a schedule.
                      </h2>
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.84rem', color: '#d4d4d8' }}>
                        We write, voice, caption, and post every video for you. Connect your YouTube, TikTok, &amp; Reels and let the AI run your channel.
                      </p>
                    </div>

                    <button
                      onClick={handleActivateAutopilot}
                      disabled={activatingAutopilot}
                      className="btn"
                      style={{
                        background: autopilotActive ? '#10b981' : 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
                        color: autopilotActive ? '#000' : '#fff',
                        border: 'none',
                        fontWeight: 800,
                        padding: '0.65rem 1.25rem',
                        borderRadius: 10,
                        fontSize: '0.84rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        boxShadow: '0 4px 14px rgba(249,115,22,0.35)',
                      }}
                    >
                      {activatingAutopilot ? <RefreshCw className="spin" size={15} /> : <CheckCircle2 size={15} />}
                      {autopilotActive ? 'Auto-Pilot Active (Posting Scheduled)' : 'Activate Auto-Pilot Channel'}
                    </button>
                  </div>
                </div>

                {/* STEP 1: PICK A TOPIC (5 Ready-Made + Custom) */}
                <div style={card}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.9rem' }}>
                    <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span style={{ width: 22, height: 22, borderRadius: '50%', background: '#f97316', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 900 }}>1</span>
                      5 Ready-Made Topics (or bring your own)
                    </h3>
                    <span style={{ fontSize: '0.72rem', color: '#a1a1aa' }}>High-retention algorithm optimized</span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.65rem' }}>
                    {FACELESS_TOPIC_PRESETS.map((t) => {
                      const isSel = selectedTopic === t.id;
                      return (
                        <div
                          key={t.id}
                          onClick={() => setSelectedTopic(t.id)}
                          style={{
                            padding: '0.85rem 1rem',
                            borderRadius: 10,
                            background: isSel ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.03)',
                            border: `1.5px solid ${isSel ? '#f97316' : 'rgba(255,255,255,0.08)'}`,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                            <span style={{ fontSize: '1.25rem' }}>{t.icon}</span>
                            <span style={{
                              fontSize: '0.62rem',
                              fontWeight: 800,
                              padding: '0.1rem 0.4rem',
                              borderRadius: 4,
                              background: isSel ? '#f97316' : 'rgba(255,255,255,0.08)',
                              color: isSel ? '#fff' : '#a1a1aa',
                            }}>
                              {t.badge}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.86rem', fontWeight: 800, color: isSel ? '#fff' : '#e4e4e7', marginBottom: '0.2rem' }}>
                            {t.title}
                          </div>
                          <p style={{ margin: 0, fontSize: '0.74rem', color: '#a1a1aa', lineHeight: 1.35 }}>
                            {t.tagline}
                          </p>
                        </div>
                      );
                    })}
                  </div>

                  {/* Custom Topic Input if Selected */}
                  {selectedTopic === 'custom' && (
                    <div style={{ marginTop: '0.85rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                      <label style={{ fontSize: '0.75rem', fontWeight: 700, color: '#f97316', display: 'block', marginBottom: '0.3rem' }}>
                        ✍️ Write Your Custom Niche / Topic for Full Control:
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Greek Mythology &amp; Dark Lore, Stoicism Secrets, True Crime, Dark Psychology..."
                        value={customTopicText}
                        onChange={(e) => setCustomTopicText(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', fontSize: '0.85rem', background: '#1c1c24', border: '1px solid rgba(249,115,22,0.4)', color: '#fff', padding: '0.55rem 0.8rem', borderRadius: 8 }}
                      />
                    </div>
                  )}
                </div>

                {/* STEP 2: VISUAL STYLE & VOICE PERSONA */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
                  {/* Visual Style */}
                  <div style={card}>
                    <h3 style={{ margin: '0 0 0.85rem', fontSize: '0.95rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span style={{ width: 22, height: 22, borderRadius: '50%', background: '#f97316', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 900 }}>2</span>
                      Pick a Visual Style
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                      {VISUAL_STYLE_PRESETS.map((s) => {
                        const isSel = selectedStyle === s.id;
                        return (
                          <div
                            key={s.id}
                            onClick={() => setSelectedStyle(s.id)}
                            style={{
                              padding: '0.65rem 0.75rem',
                              borderRadius: 8,
                              background: isSel ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.03)',
                              border: `1.5px solid ${isSel ? '#f97316' : 'rgba(255,255,255,0.08)'}`,
                              cursor: 'pointer',
                            }}
                          >
                            <div style={{ fontSize: '0.8rem', fontWeight: 800, color: isSel ? '#fff' : '#d4d4d8', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                              <span>{s.icon}</span> {s.name}
                            </div>
                            <div style={{ fontSize: '0.68rem', color: '#a1a1aa', marginTop: '0.15rem', lineHeight: 1.2 }}>{s.desc}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* AI Voice Persona */}
                  <div style={card}>
                    <h3 style={{ margin: '0 0 0.85rem', fontSize: '0.95rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span style={{ width: 22, height: 22, borderRadius: '50%', background: '#f97316', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 900 }}>3</span>
                      Pick an AI Voice Persona
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                      {VOICE_PERSONA_PRESETS.map((v) => {
                        const isSel = selectedVoice === v.id;
                        return (
                          <div
                            key={v.id}
                            onClick={() => setSelectedVoice(v.id)}
                            style={{
                              padding: '0.55rem 0.75rem',
                              borderRadius: 8,
                              background: isSel ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.03)',
                              border: `1.5px solid ${isSel ? '#f97316' : 'rgba(255,255,255,0.08)'}`,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                            }}
                          >
                            <div>
                              <div style={{ fontSize: '0.82rem', fontWeight: 800, color: isSel ? '#fff' : '#e4e4e7', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                <Volume2 size={13} color={isSel ? '#f97316' : '#a1a1aa'} /> {v.name} ({v.gender})
                              </div>
                              <div style={{ fontSize: '0.7rem', color: '#a1a1aa' }}>{v.tone}</div>
                            </div>
                            <span style={{ fontSize: '0.68rem', fontWeight: 700, color: isSel ? '#fb923c' : '#71717a' }}>{v.speed}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* STEP 3: SCHEDULE & PUBLISHING CONTROL (Public / Private / TikTok Drafts) */}
                <div style={card}>
                  <h3 style={{ margin: '0 0 0.85rem', fontSize: '0.95rem', fontWeight: 800, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <span style={{ width: 22, height: 22, borderRadius: '50%', background: '#f97316', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 900 }}>4</span>
                    Set Your Schedule &amp; Publishing Visibility
                  </h3>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                    {/* Schedule Presets */}
                    <div>
                      <label style={{ fontSize: '0.74rem', fontWeight: 700, color: '#a1a1aa', textTransform: 'uppercase', marginBottom: '0.35rem', display: 'block' }}>
                        📅 Posting Cadence
                      </label>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        {SCHEDULE_PRESETS.map((p) => (
                          <div
                            key={p.id}
                            onClick={() => setSchedulePreset(p.id)}
                            style={{
                              padding: '0.5rem 0.75rem',
                              borderRadius: 8,
                              background: schedulePreset === p.id ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.03)',
                              border: `1.5px solid ${schedulePreset === p.id ? '#f97316' : 'rgba(255,255,255,0.08)'}`,
                              cursor: 'pointer',
                            }}
                          >
                            <div style={{ fontSize: '0.8rem', fontWeight: 800, color: schedulePreset === p.id ? '#fff' : '#d4d4d8' }}>{p.label}</div>
                            <div style={{ fontSize: '0.68rem', color: '#a1a1aa' }}>{p.desc}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Publishing Visibility (Public, Private, TikTok Drafts) */}
                    <div>
                      <label style={{ fontSize: '0.74rem', fontWeight: 700, color: '#a1a1aa', textTransform: 'uppercase', marginBottom: '0.35rem', display: 'block' }}>
                        🔒 You Control How It Posts
                      </label>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        <div
                          onClick={() => setPublishingMode('PUBLIC')}
                          style={{
                            padding: '0.55rem 0.75rem',
                            borderRadius: 8,
                            background: publishingMode === 'PUBLIC' ? 'rgba(16,185,129,0.12)' : 'rgba(255,255,255,0.03)',
                            border: `1.5px solid ${publishingMode === 'PUBLIC' ? '#10b981' : 'rgba(255,255,255,0.08)'}`,
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ fontSize: '0.8rem', fontWeight: 800, color: publishingMode === 'PUBLIC' ? '#10b981' : '#d4d4d8' }}>
                            🌐 Public (Direct Publish)
                          </div>
                          <div style={{ fontSize: '0.68rem', color: '#a1a1aa' }}>Goes live immediately on YouTube Shorts, TikTok, &amp; Reels</div>
                        </div>

                        <div
                          onClick={() => setPublishingMode('PRIVATE')}
                          style={{
                            padding: '0.55rem 0.75rem',
                            borderRadius: 8,
                            background: publishingMode === 'PRIVATE' ? 'rgba(245,158,11,0.12)' : 'rgba(255,255,255,0.03)',
                            border: `1.5px solid ${publishingMode === 'PRIVATE' ? '#f59e0b' : 'rgba(255,255,255,0.08)'}`,
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ fontSize: '0.8rem', fontWeight: 800, color: publishingMode === 'PRIVATE' ? '#f59e0b' : '#d4d4d8' }}>
                            🔒 Private / Unlisted
                          </div>
                          <div style={{ fontSize: '0.68rem', color: '#a1a1aa' }}>Upload as unlisted for link-only verification before public release</div>
                        </div>

                        <div
                          onClick={() => setPublishingMode('DRAFT_REVIEW')}
                          style={{
                            padding: '0.55rem 0.75rem',
                            borderRadius: 8,
                            background: publishingMode === 'DRAFT_REVIEW' ? 'rgba(59,130,246,0.12)' : 'rgba(255,255,255,0.03)',
                            border: `1.5px solid ${publishingMode === 'DRAFT_REVIEW' ? '#3b82f6' : 'rgba(255,255,255,0.08)'}`,
                            cursor: 'pointer',
                          }}
                        >
                          <div style={{ fontSize: '0.8rem', fontWeight: 800, color: publishingMode === 'DRAFT_REVIEW' ? '#60a5fa' : '#d4d4d8' }}>
                            📱 Send to TikTok Drafts / Review Queue
                          </div>
                          <div style={{ fontSize: '0.68rem', color: '#a1a1aa' }}>Push to drafts so you can review before they go live</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Video Duration Selector */}
                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#a1a1aa' }}>⏱️ Video Length:</span>
                      {[8, 10, 15, 20, 30].map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setFacelessDuration(s)}
                          style={{
                            padding: '0.25rem 0.6rem',
                            borderRadius: 6,
                            background: facelessDuration === s ? '#f97316' : 'rgba(255,255,255,0.06)',
                            color: facelessDuration === s ? '#fff' : '#a1a1aa',
                            border: 'none',
                            fontSize: '0.75rem',
                            fontWeight: 800,
                            cursor: 'pointer',
                          }}
                        >
                          {s}s
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={handleGenerateFaceless}
                      disabled={generatingFaceless}
                      className="btn btn-primary"
                      style={{
                        background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
                        border: 'none',
                        fontWeight: 800,
                        padding: '0.65rem 1.4rem',
                        borderRadius: 10,
                        fontSize: '0.86rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        boxShadow: '0 4px 14px rgba(249,115,22,0.35)',
                      }}
                    >
                      {generatingFaceless ? <RefreshCw className="spin" size={16} /> : <Wand2 size={16} />}
                      {generatingFaceless ? 'Writing Script, Voice & Video...' : 'Generate Complete Faceless Short'}
                    </button>
                  </div>
                </div>

                {/* GENERATED FACELESS RESULT PACKAGE */}
                {facelessPackage && (
                  <div style={{ ...card, borderColor: 'rgba(249,115,22,0.3)', background: '#15151c' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.75rem' }}>
                      <div>
                        <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: '#f97316' }}>
                          ⚡ Complete Faceless Creative Package ({facelessPackage.duration_seconds}s)
                        </span>
                        <h3 style={{ margin: '0.2rem 0 0', fontSize: '1.2rem', fontWeight: 900, color: '#fff' }}>
                          {facelessPackage.title}
                        </h3>
                      </div>

                      <button
                        onClick={() => {
                          const NL = String.fromCharCode(10);
                          const SEP = NL + NL + '============================' + NL + NL;
                          const block = [
                            `TITLE: ${facelessPackage.title}`,
                            `1. SCROLL-STOPPING HOOK (0-3s):` + NL + facelessPackage.hook,
                            `2. VOICEOVER NARRATION SCRIPT (${facelessPackage.voice_persona?.name || 'Voice'}):` + NL + facelessPackage.voiceover_script,
                            `3. STARTING IMAGE PROMPT (First Frame Hook):` + NL + facelessPackage.first_frame_prompt,
                            `4. VIDEO MOTION DIFFUSION PROMPT (${facelessPackage.duration_seconds}s):` + NL + facelessPackage.video_prompt,
                            `5. ENDING CARD PROMPT:` + NL + facelessPackage.last_frame_prompt,
                            `6. VIRAL SOCIAL CAPTION & HASHTAGS:` + NL + facelessPackage.viral_caption,
                          ].join(SEP);
                          navigator.clipboard?.writeText(block);
                          showToast('Complete Creative Package copied to clipboard!');
                        }}
                        className="btn btn-primary"
                        style={{ background: '#f97316', border: 'none', fontWeight: 800, fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                      >
                        <Copy size={14} /> Copy Complete Package
                      </button>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.9rem' }}>
                      {/* Hook & Voiceover Script */}
                      <div style={{ background: '#1a1a24', padding: '0.85rem', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                          <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#f97316', textTransform: 'uppercase' }}>🎙️ Voiceover Script &amp; Hook</span>
                          <button
                            onClick={() => { navigator.clipboard?.writeText(facelessPackage.voiceover_script); showToast('Voiceover script copied'); }}
                            style={{ background: 'none', border: 'none', color: '#f97316', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                          >
                            Copy Script
                          </button>
                        </div>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fff', marginBottom: '0.4rem' }}>
                          🪝 Hook: "{facelessPackage.hook}"
                        </div>
                        <p style={{ margin: 0, fontSize: '0.78rem', color: '#d4d4d8', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                          {facelessPackage.voiceover_script}
                        </p>
                        <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: '#a1a1aa' }}>
                          🎵 <em>Music: {facelessPackage.audio_music_recommendation}</em>
                        </div>
                      </div>

                      {/* Video Motion Prompt */}
                      <div style={{ background: '#1a1a24', padding: '0.85rem', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                          <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#38bdf8', textTransform: 'uppercase' }}>🎬 Video Diffusion Prompt (Veo/Kling/Sora)</span>
                          <button
                            onClick={() => { navigator.clipboard?.writeText(facelessPackage.video_prompt); showToast('Video prompt copied'); }}
                            style={{ background: 'none', border: 'none', color: '#38bdf8', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                          >
                            Copy Video Prompt
                          </button>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.78rem', color: '#d4d4d8', lineHeight: 1.5 }}>
                          {facelessPackage.video_prompt}
                        </p>
                      </div>

                      {/* First Frame & Last Frame Image Prompts */}
                      <div style={{ background: '#1a1a24', padding: '0.85rem', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                          <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#a855f7', textTransform: 'uppercase' }}>📸 Midjourney / FLUX Stills</span>
                          <button
                            onClick={() => { navigator.clipboard?.writeText(facelessPackage.first_frame_prompt); showToast('Image prompt copied'); }}
                            style={{ background: 'none', border: 'none', color: '#a855f7', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                          >
                            Copy Start Image
                          </button>
                        </div>
                        <div style={{ fontSize: '0.76rem', color: '#e4e4e7', marginBottom: '0.4rem' }}>
                          <strong>Start Hook (0-3s):</strong> {facelessPackage.first_frame_prompt}
                        </div>
                        <div style={{ fontSize: '0.76rem', color: '#e4e4e7' }}>
                          <strong>End Outro Card:</strong> {facelessPackage.last_frame_prompt}
                        </div>
                      </div>

                      {/* Viral Social Caption */}
                      <div style={{ background: '#1a1a24', padding: '0.85rem', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                          <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#10b981', textTransform: 'uppercase' }}>✍️ Viral Caption &amp; Hashtags</span>
                          <button
                            onClick={() => { navigator.clipboard?.writeText(facelessPackage.viral_caption); showToast('Caption copied'); }}
                            style={{ background: 'none', border: 'none', color: '#10b981', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer' }}
                          >
                            Copy Caption
                          </button>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.78rem', color: '#d4d4d8', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                          {facelessPackage.viral_caption}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ========================================================================= */}
            {/* TAB 2: VIRAL VALIDATOR & VIEW PREDICTOR */}
            {/* ========================================================================= */}
            {studioTab === 'validator' && (
              <div>
                <ViralValidator
                  token={token}
                  showToast={showToast}
                  activeWorkspaceId={activeWorkspaceId}
                />

                {/* Built for Creators Value Pillars */}
                <div style={{ marginTop: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                  <div style={{ background: '#121217', borderRadius: 12, padding: '1.25rem', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <Eye size={18} color="#f97316" />
                      <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>Stop Posting Blindly</h4>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.78rem', color: '#a1a1aa', lineHeight: 1.45 }}>
                      Know exactly how your video will perform before you hit upload. Predictive algorithmic simulation based on 500M+ viral shorts.
                    </p>
                  </div>

                  <div style={{ background: '#121217', borderRadius: 12, padding: '1.25rem', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <Sparkles size={18} color="#f97316" />
                      <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>Fix Issues Instantly</h4>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.78rem', color: '#a1a1aa', lineHeight: 1.45 }}>
                      Get actionable feedback: "Shorten the intro", "Add visual cut at 0:04", "Add comment trigger CTA".
                    </p>
                  </div>

                  <div style={{ background: '#121217', borderRadius: 12, padding: '1.25rem', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <TrendingUp size={18} color="#f97316" />
                      <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>Scale Your Growth</h4>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.78rem', color: '#a1a1aa', lineHeight: 1.45 }}>
                      Consistent viral hits mean faster monetization, higher channel authority, and exponential organic reach.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* ========================================================================= */}
            {/* TAB 3: POSTSHIP MULTI-PLATFORM TEXT ENGINE (X, LINKEDIN, REDDIT) */}
            {/* ========================================================================= */}
            {studioTab === 'postship' && (
              <PostShipStudio
                token={token}
                showToast={showToast}
                activeWorkspaceId={activeWorkspaceId}
                businessName={business?.name || 'Founder'}
              />
            )}

            {/* ========================================================================= */}
            {/* TAB 4: BRAND & PRODUCT ADS STUDIO */}
            {/* ========================================================================= */}
            {studioTab === 'brand' && (
              <div>
                <div className="glass-panel" style={{ padding: '2rem', marginBottom: '1.5rem', background: '#121217', borderRadius: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '1.35rem' }}>
                    {business?.logoUrl ? (
                      <img src={business.logoUrl} alt="" style={{ width: 44, height: 44, borderRadius: 11, objectFit: 'cover' }} />
                    ) : (
                      <div style={{ width: 44, height: 44, borderRadius: 11, background: 'linear-gradient(135deg, #f97316, #ea580c)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#fff' }}>
                        {(business?.name || 'B').charAt(0).toUpperCase()}
                      </div>
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#fff' }}>{business?.name || 'Active business'}</div>
                      <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                        {business?.businessModel || 'General'}
                        {business?.brandAnalysisComplete ? ' · brand profile ready' : ' · no brand profile yet'}
                      </div>
                    </div>
                  </div>

                  {products.length > 0 && (
                    <div style={{ marginBottom: '1.25rem' }}>
                      <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        <Package size={13} style={{ verticalAlign: 'middle', marginRight: '0.35rem' }} />
                        Product (optional)
                      </label>
                      <select
                        value={productId}
                        onChange={e => setProductId(e.target.value)}
                        className="input-field"
                        style={{ width: '100%', padding: '0.7rem 0.85rem', borderRadius: 8, background: '#181820', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', fontSize: '0.9rem' }}
                      >
                        <option value="">Let the AI choose from my catalog</option>
                        {products.map(p => (
                          <option key={p.id} value={p.id}>{p.title}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 700 }}>Length:</span>
                      {[8, 10, 15, 20, 30].map(s => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setDuration(s)}
                          style={{
                            padding: '0.3rem 0.65rem',
                            borderRadius: 6,
                            background: duration === s ? '#f97316' : '#1e1e28',
                            color: duration === s ? '#fff' : '#a1a1aa',
                            border: 'none',
                            fontSize: '0.76rem',
                            fontWeight: 800,
                            cursor: 'pointer',
                          }}
                        >
                          {s}s
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={generateBrandPrompt}
                      disabled={generating}
                      className="btn btn-primary"
                      style={{ background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)', border: 'none', fontWeight: 800, padding: '0.65rem 1.35rem', borderRadius: 10 }}
                    >
                      {generating ? <RefreshCw className="spin" size={16} /> : <Wand2 size={16} />}
                      {generating ? 'Writing Prompt...' : 'Generate Brand Video Prompt'}
                    </button>
                  </div>
                </div>

                {/* Reassurance Notice */}
                <div style={{ padding: '0.75rem 1rem', borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', marginBottom: '1.5rem', fontSize: '0.8rem', color: '#a1a1aa' }}>
                  💡 Writing can take up to a minute — you can leave this page and come back; it will be in the list below.
                </div>

                {/* Prompt History Section */}
                <div style={{ marginTop: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#fff' }}>Video Prompt History</h3>
                    <button onClick={fetchHistory} style={{ background: 'none', border: 'none', color: '#f97316', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <RefreshCw size={13} /> Refresh
                    </button>
                  </div>

                  {loadingHistory ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#71717a', fontSize: '0.84rem' }}>Loading prompt history...</div>
                  ) : history.length === 0 ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#71717a', fontSize: '0.84rem', background: '#121217', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                      No video prompts generated yet. Click Generate above to create your first video brief.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {history.slice(0, 10).map((item) => (
                        <div key={item.id} style={{ ...card, padding: '0.9rem 1.1rem', background: '#14141c' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                            <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#f97316', textTransform: 'uppercase' }}>
                              {item.meta?.faceless_package ? '🚀 Faceless Short' : '🏢 Brand Video'}
                            </span>
                            <span style={{ fontSize: '0.7rem', color: '#71717a' }}>{new Date(item.createdAt).toLocaleDateString()}</span>
                          </div>
                          <p style={{ margin: '0 0 0.5rem', fontSize: '0.8rem', color: '#d4d4d8', lineHeight: 1.45 }}>
                            {item.caption || item.prompt || 'Video Creative'}
                          </p>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                              onClick={() => {
                                navigator.clipboard?.writeText(item.caption || item.prompt || '');
                                showToast('Prompt copied to clipboard');
                              }}
                              className="btn"
                              style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem', background: '#27272a', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}
                            >
                              <Copy size={12} /> Copy
                            </button>
                            <button
                              onClick={() => deletePrompt(item.id)}
                              className="btn"
                              style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem', background: 'rgba(239,68,68,0.1)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)' }}
                            >
                              <Trash2 size={12} /> Delete
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default VideoStudio;
