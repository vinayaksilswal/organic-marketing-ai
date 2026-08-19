import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE, authFetch } from '../../config';
import {
  Sparkles, Film, Copy, Check, Wand2, Package, Building2,
  AlertTriangle, Settings, Video, Image as ImageIcon,
  Upload, Trash2, RefreshCw, Clock, Send
} from 'lucide-react';

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState('');
  const [business, setBusiness] = useState(null);
  const [videoKeySet, setVideoKeySet] = useState(false);
  // 10s is the default because it is what every generator supports and
  // what a Reel audience actually finishes. Longer is offered, not urged.
  const [duration, setDuration] = useState(10);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef(null);

  // Prompt history for this business, and the attach-a-video flow that turns
  // a prompt into something the scheduler can actually post.
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
        m => m.promptType === 'video' || m.prompt || m.generationStatus
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

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  /**
   * Attach a rendered video to the prompt that produced it.
   *
   * This is the step that moves an asset into the posting cycle. A prompt row
   * carries no file, so the scheduler skips it. PATCHing the file onto the SAME
   * row keeps the prompt as the asset's base caption, which is what the caption
   * writer reads at posting time. Uploading the video as a separate row instead
   * — which this page used to do — threw that context away.
   */
  const attachVideo = async (mediaId, file) => {
    if (!file) return;
    setAttachingId(mediaId);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await authFetch(`${API_BASE}/marketing/media/${mediaId}`, {
        method: 'PATCH',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: fd,
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Upload failed (error ${res.status})`);

      showToast('Video attached. This asset is now in the posting rotation.');
      await fetchHistory();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setAttachingId(null);
      setAttachTargetId(null);
      if (attachInputRef.current) attachInputRef.current.value = '';
    }
  };

  const deletePrompt = async (mediaId) => {
    if (!window.confirm('Delete this prompt and its media?')) return;
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/${mediaId}`, {
        method: 'DELETE',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (!res.ok) throw new Error(`Could not delete (error ${res.status})`);
      showToast('Deleted.');
      await fetchHistory();
    } catch (err) {
      showToast(err.message, true);
    }
  };

  // Load the active business, its catalog, and whether a render key exists
  useEffect(() => {
    if (!activeWorkspaceId) return;
    let cancelled = false;

    (async () => {
      try {
        const [bizRes, prodRes, cfgRes] = await Promise.all([
          authFetch(`${API_BASE}/businesses`, {}, token),
          authFetch(`${API_BASE}/ecommerce/products`, { headers: { 'X-Workspace-Id': activeWorkspaceId } }, token).catch(() => null),
          authFetch(`${API_BASE}/video/config`, { headers: { 'X-Workspace-Id': activeWorkspaceId } }, token).catch(() => null),
        ]);
        if (cancelled) return;

        if (bizRes?.ok) {
          const all = await bizRes.json();
          setBusiness(Array.isArray(all) ? all.find(b => b.id === activeWorkspaceId) || null : null);
        }
        if (prodRes?.ok) {
          const p = await prodRes.json();
          setProducts(Array.isArray(p) ? p : (p?.data || []));
        }
        if (cfgRes?.ok) {
          const c = await cfgRes.json();
          setVideoKeySet(Boolean(c?.data?.apiKey));
        }
      } catch {
        /* non-fatal: the page still works without catalog or key info */
      }
    })();

    return () => { cancelled = true; };
  }, [activeWorkspaceId, token]);

  const [analyzing, setAnalyzing] = useState(false);
  const [showVideoConfig, setShowVideoConfig] = useState(false);
  const [videoProvider, setVideoProvider] = useState('json2video');
  const [videoKey, setVideoKey] = useState('');
  const [videoEndpoint, setVideoEndpoint] = useState('');
  const [savingVideoConfig, setSavingVideoConfig] = useState(false);

  const saveVideoConfig = async () => {
    if (!activeWorkspaceId) return showToast('Select a business first.', true);
    setSavingVideoConfig(true);
    try {
      const res = await authFetch(`${API_BASE}/video/config`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          provider: videoProvider,
          apiKey: videoKey,
          endpoint: videoEndpoint || null,
        }),
      }, token);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || d.message || 'Could not save the video API settings');
      }
      showToast('Video API saved. Generated prompts will now render to video automatically.');
      if (videoKey) setVideoKeySet(true);
      setVideoKey('');
      setShowVideoConfig(false);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSavingVideoConfig(false);
    }
  };

  /**
   * Build the brand profile. Onboarding runs this automatically, but if that
   * attempt failed — a rate limit, a dropped background task — the workspace
   * was stuck without one forever and every caption and video prompt came out
   * generic, with no way for the user to retry. The endpoint existed; nothing
   * in the UI called it.
   */
  const buildBrandProfile = async () => {
    if (!activeWorkspaceId) return showToast('Select a business first.', true);
    setAnalyzing(true);
    try {
      const res = await authFetch(`${API_BASE}/creatives/re-analyze`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Brand analysis failed');
      showToast('Brand profile built. Captions and prompts will now be specific to this business.');
      setBusiness(b => (b ? { ...b, brandAnalysisComplete: true } : b));
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setAnalyzing(false);
    }
  };

  const generate = async () => {
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
      // The prompt is written by a background task now, so watch the row until
      // it settles instead of holding the request open (which used to exceed
      // the server timeout and surface as a bogus CORS error).
      startPolling(data.mediaId);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setGenerating(false);
    }
  };

  const startPolling = useCallback((mediaId) => {
    if (!mediaId) return;
    let tries = 0;
    const tick = async () => {
      tries += 1;
      const rows = await fetchHistory();
      const row = (rows || []).find(m => m.id === mediaId);

      if (row?.generationStatus === 'READY') {
        showToast('Your prompt is ready.');
        return;
      }
      if (row?.generationStatus === 'FAILED') {
        showToast(row.generationError || 'Generation failed.', true);
        return;
      }
      // ~5 minutes of polling, then stop and let the row speak for itself.
      if (tries < 60) setTimeout(tick, 5000);
    };
    setTimeout(tick, 4000);
  }, [fetchHistory, showToast]);

  // Attaches to the prompt row just generated, so the prompt stays as the
  // asset's description rather than the video landing as an unlabelled file.
  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!result?.mediaId) {
      showToast('Generate a prompt first.', true);
      return;
    }
    setUploading(true);
    try {
      await attachVideo(result.mediaId, file);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const card = { background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(11, 16, 32, 0.07)', borderRadius: 12, padding: '1.1rem' };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0', maxWidth: 860 }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
            <Film color="var(--primary-color)" size={30} /> AI Video Studio
          </h1>
          <p className="text-muted" style={{ margin: '0.3rem 0 0 0', fontSize: '0.95rem' }}>
            One click. The AI reads this business's brand profile and writes a production-ready
            video prompt, then saves it to your media library.
          </p>
        </div>

        {!activeWorkspaceId ? (
          <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
            <Building2 size={26} color="var(--primary-color)" style={{ marginBottom: '0.9rem' }} />
            <p style={{ margin: 0, color: 'var(--text-muted)' }}>
              Select a business from the sidebar to generate a video for it.
            </p>
          </div>
        ) : (
          <>
            {/* The one-click panel */}
            <div className="glass-panel" style={{ padding: '2rem', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '1.35rem' }}>
                {business?.logoUrl ? (
                  <img src={business.logoUrl} alt="" style={{ width: 44, height: 44, borderRadius: 11, objectFit: 'cover' }} />
                ) : (
                  <div style={{ width: 44, height: 44, borderRadius: 11, background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#fff' }}>
                    {(business?.name || 'B').charAt(0).toUpperCase()}
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '1.05rem' }}>{business?.name || 'Active business'}</div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                    {business?.businessModel || 'General'}
                    {business?.brandAnalysisComplete ? ' · brand profile ready' : ' · no brand profile yet'}
                  </div>
                </div>
              </div>

              {business && !business.brandAnalysisComplete && (
                <div style={{ ...card, marginBottom: '1.25rem', borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.06)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem' }}>
                    <AlertTriangle size={16} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#fcd34d', marginBottom: '0.3rem' }}>
                        No brand profile for this business
                      </div>
                      <p style={{ margin: '0 0 0.85rem', fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        Without it the AI has no stored sense of your tone, audience or content
                        themes, so captions and video prompts come out generic. Building it reads
                        your website and takes about a minute.
                      </p>
                      <button className="btn btn-primary" onClick={buildBrandProfile} disabled={analyzing}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
                        {analyzing
                          ? <><span className="spinner" style={{ width: 13, height: 13 }} /> Analysing your site…</>
                          : <><Sparkles size={14} /> Build brand profile</>}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Product is optional, and only meaningful with a catalog */}
              {products.length > 0 && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    <Package size={13} style={{ verticalAlign: 'middle', marginRight: '0.35rem' }} />
                    Product <span style={{ color: 'var(--text-muted)' }}>(optional)</span>
                  </label>
                  <select
                    value={productId}
                    onChange={e => setProductId(e.target.value)}
                    style={{ width: '100%', padding: '0.7rem 0.85rem', borderRadius: 8, background: 'rgba(11, 16, 32, 0.04)', color: 'var(--text-main)', border: '1px solid var(--border-color)', fontSize: '0.9rem' }}
                  >
                    <option value="">Let the AI choose from my catalog</option>
                    {products.map(p => (
                      <option key={p.id} value={p.id}>{p.title}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Length. The generators take 8-30s now, and the prompt is
                  written to a different beat plan for each: the hook stays 3s
                  and the end card 2s whatever the length, so what actually
                  changes is how many beats sit between them. */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-muted)' }}>
                  Video length
                </label>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {[8, 10, 15, 20, 30].map((sec) => {
                    const on = duration === sec;
                    return (
                      <button
                        key={sec}
                        type="button"
                        onClick={() => setDuration(sec)}
                        aria-pressed={on}
                        style={{
                          flex: '1 1 60px', minHeight: 44, borderRadius: 10, cursor: 'pointer',
                          fontFamily: 'var(--font-family-body)', fontWeight: 700, fontSize: '0.9rem',
                          background: on ? 'var(--primary-color)' : 'rgba(11,16,32,0.04)',
                          color: on ? '#fff' : 'var(--text-main)',
                          border: `1px solid ${on ? 'var(--primary-color)' : 'var(--border-color)'}`,
                          transition: 'background .16s, color .16s, border-color .16s',
                        }}
                      >
                        {sec}s
                      </button>
                    );
                  })}
                </div>
                <p style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '0.45rem', lineHeight: 1.5 }}>
                  3s hook and a 2s end card at every length — {duration <= 10 ? 'one beat' : `${Math.ceil((duration - 5) / 8)} beats`} in between, each timed in the prompt.
                </p>
              </div>

              <button
                onClick={generate}
                disabled={generating}
                className="btn btn-primary"
                style={{ width: '100%', padding: '0.95rem', fontSize: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.55rem' }}
              >
                {generating
                  ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Generating…</>
                  : <><Wand2 size={18} /> Generate Video Prompt</>}
              </button>

              <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                {videoKeySet ? (
                  <><Video size={13} color="#10b981" /> Video rendering connected — renders are queued and saved to your media library automatically.</>
                ) : (
                  <><Settings size={13} /> No video API connected, so only the prompt is produced.</>
                )}
                <button onClick={() => setShowVideoConfig(v => !v)}
                  style={{ background: 'none', border: 'none', padding: 0, color: 'var(--primary-color)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                  {showVideoConfig ? 'Hide' : videoKeySet ? 'Change' : 'Connect a video API'}
                </button>
              </div>

              {showVideoConfig && (
                <div style={{ ...card, marginTop: '1rem' }}>
                  <h4 style={{ margin: '0 0 0.3rem', fontSize: '0.92rem' }}>Video generation API</h4>
                  <p style={{ margin: '0 0 0.9rem', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                    With a key set, generated prompts are rendered to video and saved straight to
                    this business’s media library — no manual step.
                  </p>
                  <div style={{ display: 'grid', gap: '0.7rem' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Provider</label>
                      <select value={videoProvider} onChange={e => setVideoProvider(e.target.value)}
                        style={{ width: '100%', padding: '0.6rem 0.75rem', borderRadius: 8, background: 'rgba(11, 16, 32, 0.04)', color: 'var(--text-main)', border: '1px solid var(--border-color)', fontSize: '0.88rem', appearance: 'auto' }}>
                        <option value="json2video">JSON2Video</option>
                        <option value="custom">Other (custom endpoint)</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>API key</label>
                      <input type="password" value={videoKey} onChange={e => setVideoKey(e.target.value)}
                        placeholder={videoKeySet ? '••••••••  (leave blank to keep current)' : 'Paste your API key'}
                        style={{ width: '100%', padding: '0.6rem 0.75rem', borderRadius: 8, background: 'rgba(11, 16, 32, 0.04)', color: 'var(--text-main)', border: '1px solid var(--border-color)', fontSize: '0.88rem' }} />
                    </div>
                    {videoProvider === 'custom' && (
                      <div>
                        <label style={{ display: 'block', marginBottom: '0.3rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>Endpoint URL</label>
                        <input type="url" value={videoEndpoint} onChange={e => setVideoEndpoint(e.target.value)}
                          placeholder="https://api.example.com/v1/render"
                          style={{ width: '100%', padding: '0.6rem 0.75rem', borderRadius: 8, background: 'rgba(11, 16, 32, 0.04)', color: 'var(--text-main)', border: '1px solid var(--border-color)', fontSize: '0.88rem' }} />
                      </div>
                    )}
                    <button className="btn btn-primary" onClick={saveVideoConfig} disabled={savingVideoConfig}
                      style={{ padding: '0.55rem 1rem', fontSize: '0.85rem', width: 'fit-content' }}>
                      {savingVideoConfig ? 'Saving…' : 'Save'}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Result. The prompt is written by a background task, so read the
                live row rather than the response — which no longer carries it. */}
            {result && (() => {
              const row = history.find(m => m.id === result.mediaId) || {};
              const genStatus = row.generationStatus;
              const promptText = row.prompt || row.caption || '';
              const pending = genStatus === 'PENDING' || (!promptText && genStatus !== 'FAILED');
              const failed = genStatus === 'FAILED';
              return (
              <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(11, 16, 32, 0.06)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {pending ? <span className="spinner" style={{ width: 15, height: 15 }} />
                    : failed ? <AlertTriangle size={17} color="#f87171" />
                    : <Check size={17} color="#10b981" />}
                  <h3 style={{ margin: 0, fontSize: '1.02rem' }}>
                    {pending ? `Writing a prompt for “${result.subject}”…`
                      : failed ? `Could not write a prompt for “${result.subject}”`
                      : `Prompt for “${result.subject}”`}
                  </h3>
                  <span style={{ marginLeft: 'auto', fontSize: '0.72rem', padding: '0.18rem 0.55rem', borderRadius: 999, background: 'rgba(139,92,246,0.15)', color: 'var(--primary-color)', fontWeight: 600 }}>
                    {result.usedProduct ? 'PRODUCT' : 'BRAND'}
                  </span>
                </div>

                <div style={{ padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.55rem' }}>
                    <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Video prompt
                      <span style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                        Saved to this business's media library
                      </span>
                    </label>
                    {promptText && (
                      <button
                        className="btn btn-secondary"
                        onClick={() => { navigator.clipboard.writeText(promptText); showToast('Prompt copied to clipboard'); }}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.42rem 0.85rem', fontSize: '0.82rem' }}
                      >
                        <Copy size={14} /> Copy
                      </button>
                    )}
                  </div>

                  {/* An empty textarea reads as "it generated nothing". Show
                      what is actually happening instead. */}
                  {pending ? (
                    <div style={{ ...card, display: 'flex', alignItems: 'center', gap: '0.7rem', minHeight: 110 }}>
                      <span className="spinner" style={{ width: 16, height: 16 }} />
                      <div style={{ fontSize: '0.87rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
                        Writing the prompt. Free AI providers queue under load, so this
                        can take up to a minute — you can leave this page and it will
                        still finish.
                      </div>
                    </div>
                  ) : failed ? (
                    <div style={{ ...card, borderColor: 'rgba(239,68,68,0.25)', background: 'rgba(239,68,68,0.06)' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.87rem', color: '#fca5a5', lineHeight: 1.55 }}>
                        <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                        {row.generationError || 'Generation failed. Please try again.'}
                      </div>
                      <button className="btn btn-secondary" onClick={generate} disabled={generating}
                        style={{ marginTop: '0.85rem', padding: '0.45rem 0.9rem', fontSize: '0.82rem' }}>
                        Try again
                      </button>
                    </div>
                  ) : (
                    <textarea
                      value={promptText}
                      readOnly
                      onFocus={e => e.target.select()}
                      style={{ width: '100%', minHeight: 150, padding: '1rem', fontSize: '0.9rem', lineHeight: 1.6, background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(11, 16, 32, 0.07)', borderRadius: 9, color: '#e4e4e7', resize: 'vertical' }}
                    />
                  )}

                  {/* Render outcome — absence of a key is normal, not an error */}
                  {result.render?.status === 'queued' && (
                    <div style={{ ...card, marginTop: '1.1rem', borderColor: 'rgba(16,185,129,0.25)', background: 'rgba(16,185,129,0.06)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem', color: '#6ee7b7' }}>
                        <Video size={15} /> Video render queued. It will appear in Media &amp; Catalog when it finishes.
                      </div>
                    </div>
                  )}
                  {result.render?.status === 'failed' && (
                    <div style={{ ...card, marginTop: '1.1rem', borderColor: 'rgba(239,68,68,0.25)', background: 'rgba(239,68,68,0.06)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.87rem', color: '#fca5a5' }}>
                        <AlertTriangle size={15} /> {result.render.detail} The prompt above was still saved.
                      </div>
                    </div>
                  )}

                  {/* Manual upload path — only once there is a prompt to render */}
                  {promptText && !pending && !failed && (
                    <div style={{ ...card, marginTop: '1.1rem', borderStyle: 'dashed' }}>
                      <h5 style={{ margin: '0 0 0.4rem 0', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <ImageIcon size={14} /> Made the video elsewhere?
                      </h5>
                      <p style={{ margin: '0 0 0.85rem 0', fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        Paste the prompt into Veo, Flow, Seed Dance or Runway, then upload the result
                        here. It attaches to this prompt — so the prompt becomes the video's
                        description, and the caption writer knows what is on screen.
                      </p>
                      <input type="file" accept="video/*" ref={fileInputRef} onChange={handleUpload} style={{ display: 'none' }} />
                      <button
                        className="btn btn-secondary"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1rem', fontSize: '0.85rem' }}
                      >
                        {uploading
                          ? <><span className="spinner" style={{ width: 13, height: 13 }} /> Uploading…</>
                          : <><Sparkles size={14} /> Upload video to media</>}
                      </button>
                    </div>
                  )}
                </div>
              </div>
              );
            })()}

            {/* One hidden input drives every row's attach button. */}
            <input
              type="file"
              accept="video/*,image/*"
              ref={attachInputRef}
              onChange={e => {
                const f = e.target.files?.[0];
                if (f && attachTargetId) attachVideo(attachTargetId, f);
              }}
              style={{ display: 'none' }}
            />

            {/* PROMPT LOG */}
            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden', marginTop: '1.5rem' }}>
              <div style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(11, 16, 32, 0.06)', display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
                <Clock size={16} color="var(--primary-color)" />
                <h3 style={{ margin: 0, fontSize: '1.02rem' }}>Generated prompts</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {history.length > 0 && `${history.length} total`}
                </span>
                <button
                  onClick={fetchHistory}
                  title="Refresh"
                  style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', padding: 4 }}
                >
                  <RefreshCw size={14} />
                </button>
              </div>

              {loadingHistory ? (
                <div style={{ padding: '2.5rem', textAlign: 'center' }}>
                  <span className="spinner" style={{ width: 20, height: 20 }} />
                </div>
              ) : historyError ? (
                <div style={{ padding: '2rem', textAlign: 'center' }}>
                  <AlertTriangle size={20} color="#f87171" />
                  <p style={{ margin: '0.6rem 0 0.9rem', fontSize: '0.87rem', color: '#fca5a5' }}>{historyError}</p>
                  <button className="btn btn-secondary" onClick={fetchHistory} style={{ padding: '0.42rem 0.9rem', fontSize: '0.82rem' }}>
                    Retry
                  </button>
                </div>
              ) : history.length === 0 ? (
                <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                  No prompts yet. Generate one above and it will appear here.
                </div>
              ) : (
                history.map(item => {
                  const live = item.postable === true;
                  const busy = attachingId === item.id;
                  const open = expandedId === item.id;
                  const text = item.prompt || item.caption || '';
                  // A row with no prompt used to render as an empty card with
                  // buttons and no explanation. "Writing" is only honest for a
                  // little while — past that the run is gone (a restart, or a
                  // task that died) and saying otherwise leaves the user
                  // waiting on something that will never arrive.
                  const gen = item.generationStatus;
                  const ageMins = item.createdAt
                    ? (Date.now() - new Date(item.createdAt).getTime()) / 60000
                    : 0;
                  const stalled = !text && gen !== 'FAILED' && ageMins > 12;
                  const isGenerating = !stalled && !text && gen !== 'FAILED';
                  const genFailed = gen === 'FAILED' || stalled;
                  return (
                    <div key={item.id} style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(11, 16, 32, 0.05)' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
                        {/* Thumbnail only once a real file is attached */}
                        <div style={{ width: 46, height: 46, borderRadius: 9, background: 'rgba(11, 16, 32, 0.04)', flexShrink: 0, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          {live && item.mimeType?.startsWith('video/') ? (
                            <video src={item.url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} muted />
                          ) : live ? (
                            <img src={item.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          ) : (
                            <Film size={17} color="rgba(255,255,255,0.3)" />
                          )}
                        </div>

                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
                            <span style={{
                              fontSize: '0.68rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: 4,
                              background: genFailed ? 'rgba(239,68,68,0.15)'
                                : isGenerating ? 'rgba(148,163,184,0.15)'
                                : live ? 'rgba(16,185,129,0.15)' : 'rgba(251,191,36,0.15)',
                              color: genFailed ? '#f87171'
                                : isGenerating ? '#94a3b8'
                                : live ? 'var(--success)' : '#fbbf24',
                            }}>
                              {genFailed ? 'FAILED'
                                : isGenerating ? 'WRITING…'
                                : live ? 'IN POSTING CYCLE' : 'PROMPT ONLY'}
                            </span>
                            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              {item.createdAt ? new Date(item.createdAt).toLocaleDateString() : ''}
                            </span>
                          </div>

                          {isGenerating ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                              <span className="spinner" style={{ width: 12, height: 12 }} />
                              Writing this prompt — it will appear here when it is done.
                            </div>
                          ) : genFailed ? (
                            <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: 1.55, color: '#fca5a5' }}>
                              {item.generationError
                                || (stalled
                                  ? 'This run never finished — it was interrupted. Generate again.'
                                  : 'Generation failed. Try generating again.')}
                            </p>
                          ) : (
                            <p style={{
                              margin: 0, fontSize: '0.83rem', lineHeight: 1.55, color: '#d4d4d8', fontStyle: 'italic',
                              whiteSpace: 'pre-wrap',
                              ...(open ? {} : { display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }),
                            }}>
                              {text}
                            </p>
                          )}

                          {/* The two stills the clip is generated between.
                              Shown only when the prompt is expanded, because
                              they are what you paste into an image model just
                              before you paste the prompt into a video one —
                              and the closing card is the only place the brand
                              name and the offer are rendered as real text. */}
                          {open && item.keyframes && (
                            <div style={{ marginTop: '0.9rem', display: 'grid', gap: '0.6rem' }}>
                              {[
                                ['First frame — the hook', item.keyframes.firstFramePrompt],
                                ['Last frame — the call to action', item.keyframes.lastFramePrompt],
                              ].filter(([, v]) => v).map(([label, value]) => (
                                <div key={label} style={{
                                  border: '1px solid var(--border-color)', borderRadius: 10,
                                  padding: '0.7rem 0.8rem', background: 'rgba(11,16,32,0.03)',
                                }}>
                                  <div style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    gap: '0.5rem', marginBottom: '0.35rem',
                                  }}>
                                    <span style={{ fontSize: '0.7rem', fontWeight: 800, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--primary-color)' }}>
                                      {label}
                                    </span>
                                    <button
                                      onClick={() => { navigator.clipboard?.writeText(value); showToast('Copied'); }}
                                      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.72rem', fontWeight: 600 }}
                                    >
                                      Copy
                                    </button>
                                  </div>
                                  <p style={{ margin: 0, fontSize: '0.78rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{value}</p>
                                </div>
                              ))}
                              {item.keyframes.cta && (
                                <p style={{ margin: 0, fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                                  Closing card reads <strong>{item.keyframes.brand}</strong> · {item.keyframes.cta}
                                  {item.keyframes.destination ? ` · ${item.keyframes.destination}` : ''}
                                  {item.plan?.durationSeconds ? ` — written for ${item.plan.durationSeconds}s` : ''}
                                </p>
                              )}
                            </div>
                          )}

                          {text.length > 180 && (
                            <button
                              onClick={() => setExpandedId(open ? null : item.id)}
                              style={{ background: 'none', border: 'none', padding: 0, marginTop: '0.35rem', color: 'var(--primary-color)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600 }}
                            >
                              {open ? 'Show less' : 'Show full prompt'}
                            </button>
                          )}

                          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
                            {/* Copy and attach make no sense without a prompt. */}
                            {text && (
                            <button
                              className="btn btn-secondary"
                              onClick={() => { navigator.clipboard.writeText(text); showToast('Prompt copied to clipboard'); }}
                              style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.38rem 0.75rem', fontSize: '0.78rem' }}
                            >
                              <Copy size={12} /> Copy
                            </button>
                            )}

                            {text && (
                            <button
                              className={live ? 'btn btn-secondary' : 'btn btn-primary'}
                              disabled={busy}
                              onClick={() => { setAttachTargetId(item.id); attachInputRef.current?.click(); }}
                              style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.38rem 0.75rem', fontSize: '0.78rem' }}
                            >
                              {busy
                                ? <><span className="spinner" style={{ width: 11, height: 11 }} /> Uploading…</>
                                : live
                                  ? <><Upload size={12} /> Replace video</>
                                  : <><Send size={12} /> Add video → posting cycle</>}
                            </button>
                            )}

                            <button
                              className="btn btn-secondary"
                              onClick={() => deletePrompt(item.id)}
                              style={{ padding: '0.38rem 0.55rem', color: 'var(--error)' }}
                              title="Delete"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>

                          {!live && text && (
                            <p style={{ margin: '0.6rem 0 0 0', fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                              This is a saved prompt, not a file — the scheduler skips it. Render it in
                              your video tool, then attach the result to put it in rotation.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default VideoStudio;
