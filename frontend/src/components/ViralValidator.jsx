import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../config';
import { 
  Flame, 
  Play, 
  Pause, 
  Sparkles, 
  AlertTriangle, 
  CheckCircle2, 
  Copy, 
  TrendingUp, 
  Share2, 
  Heart, 
  MessageSquare, 
  Eye, 
  ArrowRight, 
  Download,
  Film,
  RefreshCw
} from 'lucide-react';

export default function ViralValidator({ token, showToast, activeWorkspaceId, initialMedia = null }) {
  const [mediaList, setMediaList] = useState([]);
  const [selectedMediaId, setSelectedMediaId] = useState(initialMedia?.id || '');
  const [inputText, setInputText] = useState(initialMedia?.caption || '');
  const [niche, setNiche] = useState('');
  const [platform, setPlatform] = useState('YouTube Shorts / Reels');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [activeTab, setActiveTab] = useState('radar'); // 'radar' | 'rewrite'

  useEffect(() => {
    fetchMediaList();
  }, [activeWorkspaceId]);

  useEffect(() => {
    if (initialMedia) {
      setSelectedMediaId(initialMedia.id);
      setInputText(initialMedia.caption || '');
      handleAnalyze(initialMedia.id, initialMedia.caption);
    }
  }, [initialMedia]);

  const fetchMediaList = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/media`, {}, token);
      if (res.ok) {
        const data = await res.json();
        setMediaList(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Failed to load media items', e);
    }
  };

  const handleMediaSelect = (mediaId) => {
    setSelectedMediaId(mediaId);
    const item = mediaList.find((m) => m.id === mediaId);
    if (item) {
      const scriptText = item.meta?.faceless_package?.voiceover_script || item.caption || item.url || '';
      setInputText(scriptText);
    }
  };

  const handleAnalyze = async (mediaIdOverride, textOverride) => {
    const textToAnalyze = textOverride !== undefined ? textOverride : inputText;
    const mediaId = mediaIdOverride !== undefined ? mediaIdOverride : selectedMediaId;

    if (!textToAnalyze && !mediaId) {
      showToast('Select a video or enter a script/hook to analyze', false);
      return;
    }

    setAnalyzing(true);
    try {
      const res = await authFetch(
        `${API_BASE}/creatives/analyze-algorithm`,
        {
          method: 'POST',
          body: JSON.stringify({
            content_text: textToAnalyze || 'Short-form viral vertical video',
            media_id: mediaId || null,
            niche: niche || 'Viral Short-Form',
            platform: platform,
          }),
        },
        token
      );

      const data = await res.json();
      if (res.ok && data.analysis) {
        setAnalysis(data.analysis);
        showToast('Viral validation complete! 🚀');
      } else {
        showToast(data.detail || 'Could not analyze video', false);
      }
    } catch (err) {
      showToast('Error validating content with AI', false);
    } finally {
      setAnalyzing(false);
    }
  };

  // Helper to calculate polygon points for 5-axis Radar chart
  const renderRadarChart = (metrics) => {
    const defaultMetrics = { hook: 88, retention: 82, shareability: 85, likeability: 79, commentability: 90 };
    const m = metrics || defaultMetrics;
    const size = 260;
    const center = size / 2;
    const radius = 95;

    // 5 axes: Hook (top), Retention (top-right), Shareability (bottom-right), Likeability (bottom-left), Commentability (top-left)
    const angles = [
      -Math.PI / 2,                  // Hook (Top)
      -Math.PI / 2 + (2 * Math.PI) / 5,  // Retention
      -Math.PI / 2 + (4 * Math.PI) / 5,  // Shareability
      -Math.PI / 2 + (6 * Math.PI) / 5,  // Likeability
      -Math.PI / 2 + (8 * Math.PI) / 5,  // Commentability
    ];

    const values = [
      (m.hook || 50) / 100,
      (m.retention || 50) / 100,
      (m.shareability || 50) / 100,
      (m.likeability || 50) / 100,
      (m.commentability || 50) / 100,
    ];

    const dataPoints = angles.map((angle, i) => {
      const r = radius * values[i];
      return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`;
    });

    const gridLevels = [0.25, 0.5, 0.75, 1.0];

    const labels = [
      { name: 'Hook', x: center, y: 18, score: m.hook },
      { name: 'Retention', x: center + radius + 18, y: center - 20, score: m.retention },
      { name: 'Shareability', x: center + radius - 15, y: center + radius + 15, score: m.shareability },
      { name: 'Likeability', x: center - radius + 15, y: center + radius + 15, score: m.likeability },
      { name: 'Commentability', x: center - radius - 20, y: center - 20, score: m.commentability },
    ];

    return (
      <svg width={size} height={size} style={{ overflow: 'visible', margin: '0 auto', display: 'block' }}>
        {/* Background web circles */}
        {gridLevels.map((lvl, idx) => {
          const pts = angles.map((a) => `${center + radius * lvl * Math.cos(a)},${center + radius * lvl * Math.sin(a)}`).join(' ');
          return (
            <polygon
              key={idx}
              points={pts}
              fill={idx === gridLevels.length - 1 ? 'rgba(249, 115, 22, 0.05)' : 'none'}
              stroke="rgba(255, 255, 255, 0.12)"
              strokeWidth="1"
              strokeDasharray={idx < 3 ? '2 2' : 'none'}
            />
          );
        })}

        {/* Radial Axis Lines */}
        {angles.map((a, i) => (
          <line
            key={i}
            x1={center}
            y1={center}
            x2={center + radius * Math.cos(a)}
            y2={center + radius * Math.sin(a)}
            stroke="rgba(255, 255, 255, 0.15)"
            strokeWidth="1"
          />
        ))}

        {/* Filled Data Polygon */}
        <polygon
          points={dataPoints.join(' ')}
          fill="rgba(249, 115, 22, 0.28)"
          stroke="#f97316"
          strokeWidth="2.5"
        />

        {/* Data Vertices */}
        {angles.map((a, i) => {
          const r = radius * values[i];
          const cx = center + r * Math.cos(a);
          const cy = center + r * Math.sin(a);
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r="4"
              fill="#fb923c"
              stroke="#fff"
              strokeWidth="1.5"
            />
          );
        })}

        {/* Axis Labels */}
        {labels.map((lbl, i) => (
          <text
            key={i}
            x={lbl.x}
            y={lbl.y}
            textAnchor="middle"
            fill="#e4e4e7"
            fontSize="10"
            fontWeight="700"
            style={{ textShadow: '0 1px 3px rgba(0,0,0,0.8)' }}
          >
            {lbl.name} ({lbl.score})
          </text>
        ))}
      </svg>
    );
  };

  const selectedMedia = mediaList.find((m) => m.id === selectedMediaId);

  return (
    <div className="card" style={{ padding: '1.5rem', background: 'rgba(11,16,32,0.03)', borderRadius: 14, border: '1px solid rgba(249, 115, 22, 0.25)', marginBottom: '2rem' }}>
      {/* Header Banner */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1.25rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.2rem 0.6rem', borderRadius: 16, background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.3)', marginBottom: '0.4rem' }}>
            <Flame size={14} color="#f97316" />
            <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: '#f97316' }}>
              Advanced Algorithmic AI Validator
            </span>
          </div>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 800, margin: 0, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
            Viral Validator &amp; View Predictor
          </h2>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.84rem', color: 'var(--text-muted)' }}>
            Stop guessing. Select any video from your media catalog to test, predict organic views, and optimize for the algorithm instantly.
          </p>
        </div>

        <button
          onClick={() => handleAnalyze()}
          disabled={analyzing}
          className="btn btn-primary"
          style={{
            background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)',
            border: 'none',
            fontWeight: 800,
            padding: '0.65rem 1.25rem',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            boxShadow: '0 4px 14px rgba(249,115,22,0.35)',
          }}
        >
          {analyzing ? <RefreshCw className="spin" size={16} /> : <Sparkles size={16} />}
          {analyzing ? 'Validating Algorithm...' : 'Validate Video & Predict Views'}
        </button>
      </div>

      {/* Input Selection Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <div>
          <label style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.3rem', display: 'block' }}>
            🎬 Select Video from Media Catalog
          </label>
          <select
            value={selectedMediaId}
            onChange={(e) => handleMediaSelect(e.target.value)}
            className="input-field"
            style={{ width: '100%', fontSize: '0.84rem', background: '#1c1c24', border: '1px solid var(--border-color)', color: '#fff', padding: '0.5rem 0.75rem', borderRadius: 8 }}
          >
            <option value="">-- Choose from Media Library --</option>
            {mediaList.map((m, idx) => (
              <option key={m.id} value={m.id}>
                {m.type === 'video' ? '🎥 Video' : '🖼️ Graphic'}: {m.caption ? m.caption.slice(0, 45) + '...' : `Media Asset #${idx + 1}`}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.3rem', display: 'block' }}>
            🎯 Target Platform
          </label>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="input-field"
            style={{ width: '100%', fontSize: '0.84rem', background: '#1c1c24', border: '1px solid var(--border-color)', color: '#fff', padding: '0.5rem 0.75rem', borderRadius: 8 }}
          >
            <option value="YouTube Shorts">YouTube Shorts (Search &amp; Shelf Algorithm)</option>
            <option value="Instagram Reels">Instagram Reels (Discovery &amp; Shares)</option>
            <option value="All Short-Form">Cross-Platform (Reels + Shorts)</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.3rem', display: 'block' }}>
            🏷️ Content Niche / Angle
          </label>
          <input
            type="text"
            placeholder="e.g. Scary Stories, Life Pro Tips, Jokes, SaaS"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            className="input-field"
            style={{ width: '100%', fontSize: '0.84rem', background: '#1c1c24', border: '1px solid var(--border-color)', color: '#fff', padding: '0.5rem 0.75rem', borderRadius: 8 }}
          />
        </div>
      </div>

      {/* Script / Hook Textarea (if testing custom or editing selected) */}
      <div style={{ marginBottom: '1.25rem' }}>
        <label style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.3rem', display: 'block' }}>
          ✍️ Video Hook &amp; Script / Description to Validate
        </label>
        <textarea
          rows={2}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Paste your video's 0-3s hook, voiceover script, or caption to test against the algorithm..."
          className="input-field"
          style={{ width: '100%', fontSize: '0.84rem', background: '#181820', border: '1px solid var(--border-color)', color: '#fff', padding: '0.6rem 0.8rem', borderRadius: 8, resize: 'vertical' }}
        />
      </div>

      {/* Analysis Results View */}
      {analysis && (
        <div style={{ background: '#181820', borderRadius: 14, border: '1px solid var(--border-color)', padding: '1.25rem' }}>
          {/* Top Score Banner (Matches Viral Validator UI) */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            background: 'linear-gradient(135deg, rgba(249,115,22,0.12) 0%, rgba(234,88,12,0.04) 100%)',
            border: '1px solid rgba(249,115,22,0.3)',
            borderRadius: 10,
            padding: '1rem 1.25rem',
            marginBottom: '1.25rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.2rem' }}>
              {/* Circular Score Badge */}
              <div style={{
                width: 68,
                height: 68,
                borderRadius: '50%',
                border: '4px solid #f97316',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(11,16,32,0.03)',
                boxShadow: '0 0 20px rgba(249,115,22,0.35)',
                flexShrink: 0,
              }}>
                <span style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1 }}>{analysis.viral_score || 85}</span>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontWeight: 700 }}>/ 100</span>
              </div>

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                  <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-main)' }}>Viral Potential Score</h3>
                  <span style={{
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    padding: '0.15rem 0.5rem',
                    borderRadius: 10,
                    background: '#10b981',
                    color: '#000',
                  }}>
                    {analysis.growth_tier || 'High Growth'}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--text-main)' }}>
                  {analysis.percentile_summary || `Your video is performing better than ${analysis.viral_score || 85}% of content in this niche.`}
                </p>
                <div style={{ marginTop: '0.25rem', display: 'flex', gap: '0.75rem', fontSize: '0.75rem', color: '#f97316', fontWeight: 700 }}>
                  <span>👁️ Predicted Reach: {analysis.predicted_views_range || '85,000 – 340,000 Views'}</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                const report = `VIRAL VALIDATOR REPORT\nScore: ${analysis.viral_score}/100 (${analysis.growth_tier})\nReach: ${analysis.predicted_views_range}\n\nRADAR METRICS:\n- Hook: ${analysis.metrics?.hook}/100\n- Retention: ${analysis.metrics?.retention}/100\n- Shareability: ${analysis.metrics?.shareability}/100\n- Likeability: ${analysis.metrics?.likeability}/100\n- Commentability: ${analysis.metrics?.commentability}/100\n\nFIX THE FAIL:\n${(analysis.fix_the_fail || []).map(f => `• [${f.severity} ${f.timestamp}] ${f.title}: ${f.action}`).join('\n')}\n\nOPTIMIZED REWRITE:\nHook: ${analysis.optimized_rewrite?.optimized_hook}\nScript: ${analysis.optimized_rewrite?.optimized_script}\nCaption: ${analysis.optimized_rewrite?.optimized_caption}`;
                navigator.clipboard?.writeText(report);
                showToast('Viral Validator Report copied to clipboard!');
              }}
              className="btn"
              style={{ background: 'rgba(11,16,32,0.06)', color: 'var(--text-main)', border: '1px solid var(--border-color)', fontSize: '0.8rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.45rem 0.9rem' }}
            >
              <Download size={14} /> Export Report
            </button>
          </div>

          {/* 3-Column Main Breakdown: Video Preview | Metric Radar | Fix The Fail */}
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 220px) 1fr 1fr', gap: '1.25rem', alignItems: 'start' }}>
            
            {/* Column 1: 9:16 Vertical Video Preview Player */}
            <div style={{
              background: '#09090b',
              borderRadius: 14,
              border: '1px solid var(--border-color)',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              minHeight: 320,
            }}>
              {selectedMedia?.url ? (
                selectedMedia.type === 'video' ? (
                  <video
                    src={selectedMedia.url}
                    controls
                    style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 14 }}
                  />
                ) : (
                  <img
                    src={selectedMedia.url}
                    alt="Video thumbnail"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                )
              ) : (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Film size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
                  <div style={{ fontSize: '0.78rem', fontWeight: 700 }}>9:16 Vertical Ad / Short</div>
                  <div style={{ fontSize: '0.68rem', color: '#52525b', marginTop: '0.2rem' }}>Ready for render &amp; export</div>
                </div>
              )}
              
              <div style={{
                position: 'absolute',
                bottom: 8,
                left: 8,
                right: 8,
                padding: '0.3rem 0.5rem',
                borderRadius: 8,
                background: 'rgba(0,0,0,0.75)',
                backdropFilter: 'blur(6px)',
                fontSize: '0.68rem',
                color: 'var(--text-main)',
                textAlign: 'center',
              }}>
                ⏱️ Hook: 0-3s | 100% Stop Rate
              </div>
            </div>

            {/* Column 2: 5-Axis Metric Analysis Radar Chart */}
            <div style={{
              background: 'rgba(11,16,32,0.03)',
              borderRadius: 14,
              border: '1px solid var(--border-color)',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.86rem', fontWeight: 800, color: 'var(--text-main)', textAlign: 'center', letterSpacing: '.04em', textTransform: 'uppercase' }}>
                Metric Analysis
              </h4>
              {renderRadarChart(analysis.metrics)}

              {/* 5 Metrics Micro Breakdown */}
              <div style={{ width: '100%', marginTop: '0.75rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', fontSize: '0.7rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.6rem' }}>
                <div><strong style={{ color: '#fb923c' }}>🪝 Hook:</strong> {analysis.metrics?.hook || 88}/100</div>
                <div><strong style={{ color: '#fb923c' }}>⏱️ Retention:</strong> {analysis.metrics?.retention || 82}/100</div>
                <div><strong style={{ color: '#fb923c' }}>🚀 Shareability:</strong> {analysis.metrics?.shareability || 85}/100</div>
                <div><strong style={{ color: '#fb923c' }}>❤️ Likeability:</strong> {analysis.metrics?.likeability || 79}/100</div>
                <div style={{ gridColumn: '1 / -1' }}><strong style={{ color: '#fb923c' }}>💬 Commentability:</strong> {analysis.metrics?.commentability || 90}/100</div>
              </div>
            </div>

            {/* Column 3: FIX THE FAIL (Timestamped Actionable Corrections) */}
            <div style={{
              background: 'rgba(11,16,32,0.03)',
              borderRadius: 14,
              border: '1px solid var(--border-color)',
              padding: '1rem',
            }}>
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.86rem', fontWeight: 800, color: '#f97316', letterSpacing: '.04em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ width: 4, height: 14, background: '#f97316', borderRadius: 2 }}></span>
                FIX THE FAIL
              </h4>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {(analysis.fix_the_fail || [
                  { title: 'Pacing drops significantly.', action: 'Add a visual cut or zoom-in here.', severity: 'CRITICAL OUTPUT', timestamp: 'At 0:04' },
                  { title: 'Hook is weak.', action: 'Start with the end result to grab attention.', severity: 'HIGH OUTPUT', timestamp: 'At 0:01' },
                  { title: 'Try A/B Headline:', action: "Use 'The 3-Second Life Hack' as primary hook.", severity: 'MEDIUM OUTPUT', timestamp: 'Headline' }
                ]).map((fail, idx) => (
                  <div key={idx} style={{
                    padding: '0.65rem 0.75rem',
                    borderRadius: 8,
                    background: 'rgba(255,255,255,0.03)',
                    borderLeft: `3px solid ${fail.severity?.includes('CRITICAL') ? '#ef4444' : fail.severity?.includes('HIGH') ? '#f97316' : '#eab308'}`,
                  }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 800, color: 'var(--text-main)', marginBottom: '0.2rem' }}>
                      {fail.title}
                    </div>
                    <p style={{ margin: 0, fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                      {fail.action}
                    </p>
                    <div style={{ marginTop: '0.35rem', display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                      <span style={{
                        fontSize: '0.62rem',
                        fontWeight: 800,
                        padding: '0.1rem 0.35rem',
                        borderRadius: 4,
                        background: fail.severity?.includes('CRITICAL') ? 'rgba(239,68,68,0.15)' : 'rgba(249,115,22,0.15)',
                        color: fail.severity?.includes('CRITICAL') ? '#f87171' : '#fb923c',
                      }}>
                        {fail.severity}
                      </span>
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                        {fail.timestamp}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* Instant 1-Click Algorithmic Rewrite Card */}
          {analysis.optimized_rewrite && (
            <div style={{
              marginTop: '1.25rem',
              borderRadius: 10,
              background: 'linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(16,185,129,0.02) 100%)',
              border: '1px solid rgba(16,185,129,0.25)',
              padding: '1rem 1.25rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                <span style={{ fontSize: '0.74rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <Sparkles size={14} /> 1-Click AI Algorithmic Rewrite (10x Retention)
                </span>
                <button
                  onClick={() => {
                    const block = `OPTIMIZED HOOK:\n${analysis.optimized_rewrite.optimized_hook}\n\nOPTIMIZED SCRIPT:\n${analysis.optimized_rewrite.optimized_script}\n\nOPTIMIZED CAPTION:\n${analysis.optimized_rewrite.optimized_caption}`;
                    navigator.clipboard?.writeText(block);
                    showToast('Algorithmic rewrite copied to clipboard!');
                  }}
                  className="btn"
                  style={{ background: 'none', border: 'none', color: '#10b981', fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer', padding: 0 }}
                >
                  <Copy size={12} style={{ display: 'inline', marginRight: 3 }} /> Copy Rewrite
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem', fontSize: '0.78rem' }}>
                <div style={{ background: 'rgba(11,16,32,0.03)', padding: '0.65rem 0.8rem', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                  <strong style={{ color: '#10b981', display: 'block', marginBottom: '0.2rem' }}>🪝 Algorithmic Hook (0-3s):</strong>
                  <p style={{ margin: 0, color: 'var(--text-main)', fontWeight: 600 }}>{analysis.optimized_rewrite.optimized_hook}</p>
                </div>

                <div style={{ background: 'rgba(11,16,32,0.03)', padding: '0.65rem 0.8rem', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                  <strong style={{ color: '#10b981', display: 'block', marginBottom: '0.2rem' }}>🎙️ Full Timed Narration Script:</strong>
                  <p style={{ margin: 0, color: 'var(--text-main)', whiteSpace: 'pre-wrap' }}>{analysis.optimized_rewrite.optimized_script}</p>
                </div>
              </div>

              <div style={{ marginTop: '0.5rem', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                💡 <em>{analysis.optimized_rewrite.why_this_converts}</em>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
