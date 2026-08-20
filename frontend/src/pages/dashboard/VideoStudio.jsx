import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE, authFetch } from '../../config';
import {
  Sparkles, Film, Copy, Check, Wand2, Package, Building2,
  AlertTriangle, Video, Image as ImageIcon,
  Upload, Trash2, RefreshCw, Clock, Send, CheckCircle2, ArrowRight,
  TrendingUp, Shield, BarChart3, HelpCircle, Layers, Volume2, Globe, Eye
} from 'lucide-react';
import { useWorkspace } from '../../components/WorkspaceContext';

const CREATIVE_GOALS = [
  { id: 'conversion', name: 'Direct Conversion', desc: 'Direct response sales, irresistible offer & strong CTA', icon: '🎯' },
  { id: 'problem_agitation_solution', name: 'Problem-Agitation-Solution', desc: 'Opens on acute pain, agitates problem, resolves with product', icon: '⚡' },
  { id: 'challenger_comparison', name: 'Challenger Upgrade', desc: 'Frustrating old manual way vs. effortless new way', icon: '⚔️' },
  { id: 'product_demo', name: 'Product Demo & Showcase', desc: 'Clean UI screen walk-through with smooth camera pan', icon: '📱' },
  { id: 'lifestyle_integration', name: 'Lifestyle Aspiration', desc: 'High-end visual aesthetic, editorial lighting, aspirational mood', icon: '✨' },
];

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  const { activeWorkspace, workspaces } = useWorkspace();
  const currentWorkspace = activeWorkspace || workspaces?.find(w => w.id === activeWorkspaceId) || workspaces?.[0] || null;
  const businessName = currentWorkspace?.name || 'Active Business';

  // Form State
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState('');
  const [goal, setGoal] = useState('conversion');
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [customBrief, setCustomBrief] = useState('');
  const [generating, setGenerating] = useState(false);
  const [latestCreative, setLatestCreative] = useState(null);

  // History State
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [copiedKey, setCopiedKey] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const fetchHistory = useCallback(async () => {
    if (!activeWorkspaceId) return;
    setLoadingHistory(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (res.ok) {
        const data = await res.json();
        const videoPrompts = Array.isArray(data) ? data.filter(m => m.promptType === 'video' || m.prompt || m.caption) : [];
        setHistory(videoPrompts);
      }
    } catch (err) {
      console.error('Failed to fetch prompt history', err);
    } finally {
      setLoadingHistory(false);
    }
  }, [activeWorkspaceId, token]);

  const fetchProducts = useCallback(async () => {
    if (!activeWorkspaceId) return;
    try {
      const res = await authFetch(`${API_BASE}/marketing/products`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (res.ok) {
        const data = await res.json();
        setProducts(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('Failed to fetch products', err);
    }
  }, [activeWorkspaceId, token]);

  useEffect(() => {
    fetchHistory();
    fetchProducts();
  }, [fetchHistory, fetchProducts]);

  const handleGenerate = async () => {
    if (!activeWorkspaceId) {
      showToast('Please select a business workspace first.', true);
      return;
    }

    setGenerating(true);
    setLatestCreative(null);

    try {
      const res = await authFetch(`${API_BASE}/creatives/auto-video`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          product_id: productId || null,
          goal: goal,
          duration_seconds: duration,
        }),
      }, token);

      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Generation failed');

      showToast('Writing your 3-part video creative prompts... 🚀');
      
      // Poll briefly to pick up the newly generated media asset
      let attempts = 0;
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          const mediaRes = await authFetch(`${API_BASE}/marketing/media`, {
            headers: { 'X-Workspace-Id': activeWorkspaceId },
          }, token);
          if (mediaRes.ok) {
            const list = await mediaRes.json();
            const newest = Array.isArray(list) ? list.find(m => m.id === data.mediaId) || list[0] : null;
            if (newest && newest.prompt && newest.generationStatus !== 'PENDING') {
              setLatestCreative(newest);
              clearInterval(pollInterval);
              setGenerating(false);
              showToast('✨ 2 Image Prompts + 1 Video Prompt generated successfully!');
              await fetchHistory();
            }
          }
        } catch (e) {}

        if (attempts > 20) {
          clearInterval(pollInterval);
          setGenerating(false);
          await fetchHistory();
        }
      }, 2500);

    } catch (err) {
      showToast(err.message, true);
      setGenerating(false);
    }
  };

  const copyToClipboard = (text, key, label) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(key);
    showToast(`${label} copied to clipboard!`);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  const deletePrompt = async (id) => {
    if (!window.confirm('Delete this video creative brief?')) return;
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/${id}`, {
        method: 'DELETE',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (res.ok) {
        showToast('Video prompt deleted');
        setHistory(prev => prev.filter(p => p.id !== id));
        if (latestCreative?.id === id) setLatestCreative(null);
      }
    } catch (e) {
      showToast('Could not delete prompt', true);
    }
  };

  // Helper to extract clean keyframe prompts
  const getKeyframePrompts = (item) => {
    const kf = item?.keyframes || {};
    const firstFrame = kf.firstFramePrompt || (
      item?.prompt
        ? `Editorial photograph, vertical ${aspectRatio}, close on ${item.prompt.slice(0, 100)}, natural ambient lighting, shallow depth of field, photographic, sharp focus, no text`
        : `Editorial photograph, vertical 9:16, high-energy product launch visual for ${businessName}, ambient lighting, sharp focus, no text`
    );

    const videoPrompt = item?.prompt || item?.caption || `Cinematic camera push-in on ${businessName} hero showcase, smooth motion blur, 8k resolution, high dynamic range, continuous action.`;

    const lastFrame = kf.lastFramePrompt || (
      `A minimal vertical ${aspectRatio} end card, flat solid background, no photograph: the brand name "${businessName}" in bold clean sans-serif type, centred, below it "Start free at ${businessName}". Sharp focus, clean poster design`
    );

    return { firstFrame, videoPrompt, lastFrame };
  };

  const activeDisplayCreative = latestCreative || (history.length > 0 ? history[0] : null);
  const activePrompts = activeDisplayCreative ? getKeyframePrompts(activeDisplayCreative) : null;

  return (
    <div className="view">
      <div className="container" style={{ padding: '2.5rem 0', maxWidth: 1040 }}>
        
        {/* Header Section */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(249, 115, 22, 0.08) 0%, rgba(234, 88, 12, 0.03) 100%)',
          borderRadius: 16,
          padding: '1.75rem 2rem',
          border: '1px solid rgba(249, 115, 22, 0.25)',
          marginBottom: '2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1.25rem',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.2rem 0.65rem',
                borderRadius: 20,
                background: 'rgba(249,115,22,0.12)',
                border: '1px solid rgba(249,115,22,0.3)',
                fontSize: '0.72rem',
                fontWeight: 800,
                color: '#f97316',
                textTransform: 'uppercase',
                letterSpacing: '.06em',
              }}>
                <Video size={13} /> Brand Video Prompt Generator
              </span>

              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                padding: '0.2rem 0.65rem',
                borderRadius: 20,
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                fontSize: '0.72rem',
                fontWeight: 800,
                color: '#fff',
              }}>
                <Building2 size={12} /> Active: {businessName}
              </span>
            </div>

            <h1 style={{ fontSize: '1.75rem', fontWeight: 900, margin: '0 0 0.35rem', color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
              Brand Ads Video Prompt Studio
            </h1>
            <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--text-muted)' }}>
              Generates the complete 3-part production brief for every video creative: <strong style={{ color: 'var(--text-main)' }}>Two Image Prompts</strong> (Opening Keyframe + Closing CTA Outro) and <strong style={{ color: 'var(--text-main)' }}>One Video Motion Prompt</strong>.
            </p>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="btn btn-primary"
            style={{
              background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
              border: 'none',
              fontWeight: 800,
              padding: '0.75rem 1.4rem',
              borderRadius: 10,
              fontSize: '0.9rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: '0 4px 16px rgba(249,115,22,0.35)',
              cursor: 'pointer',
            }}
          >
            {generating ? <RefreshCw className="spin" size={16} /> : <Wand2 size={16} />}
            {generating ? 'Compiling Video Brief...' : 'Generate 2 Image + 1 Video Prompt'}
          </button>
        </div>

        {/* Generator Controls Card */}
        <div className="card" style={{ padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 16, border: '1px solid var(--border-color)', marginBottom: '2rem' }}>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem', marginBottom: '1.25rem' }}>
            
            {/* Subject Selector (Product vs Whole Brand) */}
            <div>
              <label style={{ fontSize: '0.76rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', display: 'block' }}>
                📦 Product / Creative Subject
              </label>
              <select
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                className="input-field"
                style={{ width: '100%', fontSize: '0.84rem', padding: '0.55rem 0.75rem', borderRadius: 8 }}
              >
                <option value="">🏢 Entire Business ({businessName})</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    🛍️ {p.title || p.name} {p.price ? `($${p.price})` : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Creative Goal */}
            <div>
              <label style={{ fontSize: '0.76rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', display: 'block' }}>
                🎯 Marketing Angle &amp; Goal
              </label>
              <select
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                className="input-field"
                style={{ width: '100%', fontSize: '0.84rem', padding: '0.55rem 0.75rem', borderRadius: 8 }}
              >
                {CREATIVE_GOALS.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.icon} {g.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Duration Selector */}
            <div>
              <label style={{ fontSize: '0.76rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', display: 'block' }}>
                ⏱️ Video Length
              </label>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                {[8, 10, 15, 20, 30].map((sec) => (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => setDuration(sec)}
                    style={{
                      flex: 1,
                      padding: '0.5rem 0',
                      borderRadius: 8,
                      background: duration === sec ? '#f97316' : 'rgba(11, 16, 32, 0.04)',
                      color: duration === sec ? '#fff' : 'var(--text-main)',
                      border: `1px solid ${duration === sec ? '#f97316' : 'var(--border-color)'}`,
                      fontSize: '0.78rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {sec}s
                  </button>
                ))}
              </div>
            </div>

            {/* Aspect Ratio */}
            <div>
              <label style={{ fontSize: '0.76rem', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.4rem', display: 'block' }}>
                📐 Aspect Ratio
              </label>
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                {[
                  { label: '9:16 (Reels/Shorts)', value: '9:16' },
                  { label: '16:9 (YouTube)', value: '16:9' },
                  { label: '1:1 (Square)', value: '1:1' },
                ].map((ar) => (
                  <button
                    key={ar.value}
                    type="button"
                    onClick={() => setAspectRatio(ar.value)}
                    style={{
                      flex: 1,
                      padding: '0.5rem 0',
                      borderRadius: 8,
                      background: aspectRatio === ar.value ? '#f97316' : 'rgba(11, 16, 32, 0.04)',
                      color: aspectRatio === ar.value ? '#fff' : 'var(--text-main)',
                      border: `1px solid ${aspectRatio === ar.value ? '#f97316' : 'var(--border-color)'}`,
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {ar.label.split(' ')[0]}
                  </button>
                ))}
              </div>
            </div>

          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.85rem', borderTop: '1px solid var(--border-color)', flexWrap: 'wrap', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              ⚡ AI will write the 1st frame still prompt, the video motion prompt, and the closing CTA frame for <strong style={{ color: 'var(--text-main)' }}>{businessName}</strong>.
            </span>

            <button
              onClick={handleGenerate}
              disabled={generating}
              className="btn btn-primary"
              style={{
                background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
                border: 'none',
                fontWeight: 800,
                padding: '0.55rem 1.25rem',
                borderRadius: 8,
                fontSize: '0.84rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                cursor: 'pointer',
              }}
            >
              {generating ? <RefreshCw className="spin" size={14} /> : <Sparkles size={14} />}
              {generating ? 'Generating 3 Prompts...' : 'Generate Video Creative'}
            </button>
          </div>

          {/* A spinner with no expectation set is why people reload and
              generate twice, paying for the same brief again. It says how long
              and that leaving is safe -- never WHY it is slow, which is ours. */}
          {generating && (
            <div style={{
              marginTop: '1rem', padding: '0.8rem 0.95rem', borderRadius: 10,
              background: 'rgba(109,40,217,0.06)', border: '1px solid rgba(109,40,217,0.18)',
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5,
            }}>
              <RefreshCw className="spin" size={15} style={{ flexShrink: 0, color: 'var(--primary-color)' }} />
              <span>
                Writing your three prompts — this can take up to a minute. You can
                leave this page and it will still finish.
              </span>
            </div>
          )}
        </div>

        {/* Generated Creative Prompts Output (2 Image Prompts + 1 Video Prompt) */}
        {activePrompts && (
          <div style={{ marginBottom: '2.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ width: 4, height: 18, background: '#f97316', borderRadius: 2 }}></span>
                <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  Generated Video Creative: 2 Image Prompts + 1 Video Prompt
                </h3>
              </div>

              <button
                onClick={() => {
                  const fullBundle = `=== VIDEO CREATIVE BRIEF FOR ${businessName} ===\n\n1. FIRST FRAME IMAGE PROMPT (Opening Still):\n${activePrompts.firstFrame}\n\n2. VIDEO MOTION PROMPT (0:00 - ${duration}s):\n${activePrompts.videoPrompt}\n\n3. LAST FRAME IMAGE PROMPT (Outro CTA Screen):\n${activePrompts.lastFrame}\n\n4. SPOKEN VOICEOVER / CAPTION:\n${activeDisplayCreative?.caption || activePrompts.videoPrompt}`;
                  copyToClipboard(fullBundle, 'all', 'Complete Creative Bundle');
                }}
                className="btn"
                style={{
                  background: copiedKey === 'all' ? 'rgba(16,185,129,0.15)' : 'rgba(249,115,22,0.12)',
                  color: copiedKey === 'all' ? '#10b981' : '#f97316',
                  border: `1px solid ${copiedKey === 'all' ? '#10b981' : 'rgba(249,115,22,0.3)'}`,
                  fontSize: '0.8rem',
                  fontWeight: 800,
                  padding: '0.45rem 0.9rem',
                  borderRadius: 8,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
              >
                {copiedKey === 'all' ? <Check size={14} /> : <Copy size={14} />}
                {copiedKey === 'all' ? 'Copied Full Bundle!' : 'Copy Complete 3-Prompt Bundle'}
              </button>
            </div>

            {/* The 3 Core Prompt Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))', gap: '1.25rem', alignItems: 'stretch' }}>
              
              {/* CARD 1: FIRST FRAME IMAGE PROMPT */}
              <div style={{
                background: '#121217',
                borderRadius: 14,
                border: '1px solid rgba(59, 130, 246, 0.35)',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.76rem', fontWeight: 800, color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '.04em', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      🖼️ Image Prompt 1: First Frame Still (0:00)
                    </span>
                    <span style={{ fontSize: '0.68rem', color: '#a1a1aa', fontWeight: 700 }}>Starting Look</span>
                  </div>

                  <p style={{ margin: '0 0 1rem', fontSize: '0.82rem', color: '#e4e4e7', lineHeight: 1.5, fontFamily: 'monospace, sans-serif' }}>
                    {activePrompts.firstFrame}
                  </p>
                </div>

                <div style={{ paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.7rem', color: '#71717a' }}>Midjourney / Flux / Ideogram</span>
                  <button
                    onClick={() => copyToClipboard(activePrompts.firstFrame, 'img1', 'First Frame Image Prompt')}
                    className="btn"
                    style={{
                      background: copiedKey === 'img1' ? 'rgba(16,185,129,0.2)' : 'rgba(59,130,246,0.15)',
                      color: copiedKey === 'img1' ? '#10b981' : '#60a5fa',
                      border: '1px solid rgba(59,130,246,0.3)',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      padding: '0.3rem 0.7rem',
                      borderRadius: 6,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                    }}
                  >
                    {copiedKey === 'img1' ? <Check size={12} /> : <Copy size={12} />}
                    {copiedKey === 'img1' ? 'Copied!' : 'Copy Image Prompt 1'}
                  </button>
                </div>
              </div>

              {/* CARD 2: VIDEO MOTION PROMPT */}
              <div style={{
                background: '#121217',
                borderRadius: 14,
                border: '1px solid rgba(249, 115, 22, 0.4)',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: '0 4px 20px rgba(249,115,22,0.15)',
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.76rem', fontWeight: 800, color: '#f97316', textTransform: 'uppercase', letterSpacing: '.04em', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      🎥 Video Prompt: Motion &amp; Action (0-10s)
                    </span>
                    <span style={{ fontSize: '0.68rem', color: '#fb923c', fontWeight: 800 }}>Core Prompt</span>
                  </div>

                  <p style={{ margin: '0 0 1rem', fontSize: '0.82rem', color: '#fff', lineHeight: 1.55, fontFamily: 'monospace, sans-serif' }}>
                    {activePrompts.videoPrompt}
                  </p>
                </div>

                <div style={{ paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.7rem', color: '#71717a' }}>Kling / Runway Gen-3 / Luma / Sora</span>
                  <button
                    onClick={() => copyToClipboard(activePrompts.videoPrompt, 'vid', 'Video Motion Prompt')}
                    className="btn"
                    style={{
                      background: copiedKey === 'vid' ? 'rgba(16,185,129,0.2)' : 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
                      color: '#fff',
                      border: 'none',
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      padding: '0.3rem 0.75rem',
                      borderRadius: 6,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                    }}
                  >
                    {copiedKey === 'vid' ? <Check size={12} /> : <Copy size={12} />}
                    {copiedKey === 'vid' ? 'Copied!' : 'Copy Video Prompt'}
                  </button>
                </div>
              </div>

              {/* CARD 3: LAST FRAME IMAGE PROMPT (OUTRO CTA) */}
              <div style={{
                background: '#121217',
                borderRadius: 14,
                border: '1px solid rgba(16, 185, 129, 0.35)',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.76rem', fontWeight: 800, color: '#10b981', textTransform: 'uppercase', letterSpacing: '.04em', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      🖼️ Image Prompt 2: Last Frame Outro (End)
                    </span>
                    <span style={{ fontSize: '0.68rem', color: '#a1a1aa', fontWeight: 700 }}>Brand &amp; CTA Still</span>
                  </div>

                  <p style={{ margin: '0 0 1rem', fontSize: '0.82rem', color: '#e4e4e7', lineHeight: 1.5, fontFamily: 'monospace, sans-serif' }}>
                    {activePrompts.lastFrame}
                  </p>
                </div>

                <div style={{ paddingTop: '0.75rem', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.7rem', color: '#71717a' }}>Readable Brand Offer</span>
                  <button
                    onClick={() => copyToClipboard(activePrompts.lastFrame, 'img2', 'Last Frame Image Prompt')}
                    className="btn"
                    style={{
                      background: copiedKey === 'img2' ? 'rgba(16,185,129,0.2)' : 'rgba(16,185,129,0.15)',
                      color: copiedKey === 'img2' ? '#10b981' : '#34d399',
                      border: '1px solid rgba(16,185,129,0.3)',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      padding: '0.3rem 0.7rem',
                      borderRadius: 6,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                    }}
                  >
                    {copiedKey === 'img2' ? <Check size={12} /> : <Copy size={12} />}
                    {copiedKey === 'img2' ? 'Copied!' : 'Copy Image Prompt 2'}
                  </button>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* Video Prompt History */}
        <div style={{ marginTop: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Clock size={16} color="var(--primary-color)" />
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-main)' }}>
                Brand Video Prompt Library
              </h3>
            </div>
            <button
              onClick={fetchHistory}
              style={{ background: 'none', border: 'none', color: '#f97316', fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
            >
              <RefreshCw size={13} /> Refresh Library
            </button>
          </div>

          {loadingHistory ? (
            <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
              Loading video prompt library...
            </div>
          ) : history.length === 0 ? (
            <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.88rem', background: 'var(--bg-card)', borderRadius: 14, border: '1px solid var(--border-color)' }}>
              No video prompts generated yet for {businessName}. Click "Generate Video Creative" above to create your first brief!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {history.map((item) => {
                const prompts = getKeyframePrompts(item);
                const isExpanded = expandedId === item.id;

                return (
                  <div
                    key={item.id}
                    style={{
                      background: '#121217',
                      borderRadius: 14,
                      border: '1px solid rgba(255,255,255,0.08)',
                      padding: '1.25rem',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.65rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.74rem', fontWeight: 800, padding: '0.15rem 0.55rem', borderRadius: 6, background: 'rgba(249,115,22,0.15)', color: '#f97316' }}>
                          🎥 2 Img + 1 Vid Creative
                        </span>
                        <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#fff' }}>
                          {item.filename || `Video Brief — ${businessName}`}
                        </span>
                      </div>
                      <span style={{ fontSize: '0.72rem', color: '#71717a' }}>
                        {item.createdAt ? new Date(item.createdAt).toLocaleDateString() : ''}
                      </span>
                    </div>

                    {/* Core Video Motion Snippet */}
                    <div style={{ background: '#090a0f', padding: '0.75rem 1rem', borderRadius: 8, border: '1px solid rgba(255,255,255,0.06)', marginBottom: '0.75rem' }}>
                      <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#fb923c', textTransform: 'uppercase', display: 'block', marginBottom: '0.2rem' }}>
                        🎥 Video Motion Prompt:
                      </span>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: '#d4d4d8', lineHeight: 1.45 }}>
                        {item.prompt || item.caption}
                      </p>
                    </div>

                    {/* Expandable 2 Image Prompts (First Frame + Last Frame) */}
                    {isExpanded && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem', fontSize: '0.76rem' }}>
                        <div style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)', padding: '0.65rem 0.8rem', borderRadius: 8 }}>
                          <strong style={{ color: '#60a5fa', display: 'block', marginBottom: '0.2rem' }}>🖼️ First Frame Image Prompt:</strong>
                          <p style={{ margin: 0, color: '#cbd5e1', lineHeight: 1.4 }}>{prompts.firstFrame}</p>
                        </div>

                        <div style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.2)', padding: '0.65rem 0.8rem', borderRadius: 8 }}>
                          <strong style={{ color: '#34d399', display: 'block', marginBottom: '0.2rem' }}>🖼️ Last Frame Image Prompt (CTA):</strong>
                          <p style={{ margin: 0, color: '#cbd5e1', lineHeight: 1.4 }}>{prompts.lastFrame}</p>
                        </div>
                      </div>
                    )}

                    {/* Action Footer */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.5rem', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : item.id)}
                        style={{ background: 'none', border: 'none', color: '#a1a1aa', fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer', padding: 0 }}
                      >
                        {isExpanded ? '▲ Hide 2 Image Keyframe Prompts' : '▼ View 2 Image Keyframe Prompts'}
                      </button>

                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button
                          onClick={() => {
                            const full = `1. FIRST FRAME IMAGE PROMPT:\n${prompts.firstFrame}\n\n2. VIDEO MOTION PROMPT:\n${prompts.videoPrompt}\n\n3. LAST FRAME IMAGE PROMPT:\n${prompts.lastFrame}`;
                            copyToClipboard(full, `hist-${item.id}`, 'Creative Bundle');
                          }}
                          className="btn"
                          style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem', background: '#27272a', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6 }}
                        >
                          <Copy size={11} /> {copiedKey === `hist-${item.id}` ? 'Copied!' : 'Copy All 3 Prompts'}
                        </button>
                        <button
                          onClick={() => deletePrompt(item.id)}
                          className="btn"
                          style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem', background: 'rgba(239,68,68,0.1)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6 }}
                        >
                          <Trash2 size={11} /> Delete
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default VideoStudio;
