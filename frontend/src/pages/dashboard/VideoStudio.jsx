import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../config';
import {
  Sparkles, Film, Copy, Check, Wand2, Package, Building2,
  AlertTriangle, Settings, Video, Image as ImageIcon
} from 'lucide-react';

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState('');
  const [business, setBusiness] = useState(null);
  const [videoKeySet, setVideoKeySet] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef(null);

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
        body: JSON.stringify({ product_id: productId || null, goal: 'conversion' }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Generation failed');

      setResult(data);
      const r = data.render || {};
      if (r.status === 'queued') showToast('Prompt generated and video render queued.');
      else if (r.status === 'failed') showToast('Prompt saved, but the video render failed.', true);
      else showToast('Prompt generated and saved to your media library.');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setGenerating(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/upload-media`, {
        method: 'POST',
        body: fd,
        headers: { Authorization: `Bearer ${token}`, 'X-Workspace-Id': activeWorkspaceId || '' },
      });
      if (!res.ok) throw new Error('Upload failed');
      showToast('Video added to your media library.');
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setUploading(false);
    }
  };

  const card = { background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, padding: '1.1rem' };

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
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.6)' }}>
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
                  <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.45)' }}>
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
                      <p style={{ margin: '0 0 0.85rem', fontSize: '0.82rem', color: 'rgba(255,255,255,0.6)', lineHeight: 1.5 }}>
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
                  <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)' }}>
                    <Package size={13} style={{ verticalAlign: 'middle', marginRight: '0.35rem' }} />
                    Product <span style={{ color: 'rgba(255,255,255,0.35)' }}>(optional)</span>
                  </label>
                  <select
                    value={productId}
                    onChange={e => setProductId(e.target.value)}
                    style={{ width: '100%', padding: '0.7rem 0.85rem', borderRadius: 8, background: 'rgba(255,255,255,0.04)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', fontSize: '0.9rem' }}
                  >
                    <option value="">Let the AI choose from my catalog</option>
                    {products.map(p => (
                      <option key={p.id} value={p.id}>{p.title}</option>
                    ))}
                  </select>
                </div>
              )}

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

              <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem', color: 'rgba(255,255,255,0.42)' }}>
                {videoKeySet ? (
                  <><Video size={13} color="#10b981" /> Video rendering is connected — a video will be queued automatically.</>
                ) : (
                  <><Settings size={13} /> No video API key set, so only the prompt is produced. Take it to Veo or Seed Dance, then upload the result below.</>
                )}
              </div>
            </div>

            {/* Result */}
            {result && (
              <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Check size={17} color="#10b981" />
                  <h3 style={{ margin: 0, fontSize: '1.02rem' }}>
                    Prompt for “{result.subject}”
                  </h3>
                  <span style={{ marginLeft: 'auto', fontSize: '0.72rem', padding: '0.18rem 0.55rem', borderRadius: 999, background: 'rgba(139,92,246,0.15)', color: 'var(--primary-color)', fontWeight: 600 }}>
                    {result.usedProduct ? 'PRODUCT' : 'BRAND'}
                  </span>
                </div>

                <div style={{ padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.55rem' }}>
                    <label style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)' }}>
                      Video prompt
                      <span style={{ display: 'block', fontSize: '0.75rem', color: 'rgba(255,255,255,0.4)', marginTop: '0.1rem' }}>
                        Saved to this business's media library
                      </span>
                    </label>
                    <button
                      className="btn btn-secondary"
                      onClick={() => { navigator.clipboard.writeText(result.veo_prompt); showToast('Prompt copied to clipboard'); }}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.42rem 0.85rem', fontSize: '0.82rem' }}
                    >
                      <Copy size={14} /> Copy
                    </button>
                  </div>

                  <textarea
                    value={result.veo_prompt}
                    readOnly
                    onFocus={e => e.target.select()}
                    style={{ width: '100%', minHeight: 150, padding: '1rem', fontSize: '0.9rem', lineHeight: 1.6, background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 9, color: '#e4e4e7', resize: 'vertical' }}
                  />

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

                  {/* Manual upload path when there is no render key */}
                  {result.render?.status !== 'queued' && (
                    <div style={{ ...card, marginTop: '1.1rem', borderStyle: 'dashed' }}>
                      <h5 style={{ margin: '0 0 0.4rem 0', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <ImageIcon size={14} /> Made the video elsewhere?
                      </h5>
                      <p style={{ margin: '0 0 0.85rem 0', fontSize: '0.82rem', color: 'rgba(255,255,255,0.5)', lineHeight: 1.5 }}>
                        Paste the prompt into Veo, Seed Dance, or Runway, then upload the result here
                        so the scheduler can post it.
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
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default VideoStudio;
