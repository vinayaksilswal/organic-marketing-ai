import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { Settings, Play, Code, Copy, Sparkles, Check, Film, Key, Globe, LayoutTemplate } from 'lucide-react';

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  const [provider, setProvider] = useState('json2video');
  const [apiKey, setApiKey] = useState('');
  
  // Pipeline inputs
  const [productName, setProductName] = useState('');
  const [productUrl, setProductUrl] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  
  // Outputs
  const [intelligence, setIntelligence] = useState(null);
  const [veoPrompt, setVeoPrompt] = useState('');
  const [jsonPayload, setJsonPayload] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [projectUrl, setProjectUrl] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, [activeWorkspaceId]);

  const fetchConfig = async () => {
    try {
      const res = await authFetch(`${API_BASE}/video/config`, {}, token);
      if (res.ok) {
        const body = await res.json();
        if (body.data) {
          setProvider(body.data.provider || 'json2video');
          setApiKey(body.data.apiKey || '');
        }
      }
    } catch (err) {
      console.error('Failed to load video config', err);
    }
  };

  const saveConfig = async () => {
    setConfigLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/video/config`, {
        method: 'POST',
        body: JSON.stringify({ provider, apiKey })
      }, token);
      if (res.ok) {
        showToast('Video API Configuration Saved!');
      } else {
        throw new Error('Failed to save configuration');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setConfigLoading(false);
    }
  };

  const generateCampaign = async () => {
    if (!productName || !productUrl || !imageUrl) {
      return showToast('Please provide Product Name, URL, and Image URL', true);
    }
    
    setLoading(true);
    setJobId(null);
    setProjectUrl(null);
    try {
      const res = await authFetch(`${API_BASE}/creatives/generate-video-campaign`, {
        method: 'POST',
        body: JSON.stringify({ 
          product_name: productName, 
          product_url: productUrl, 
          image_url: imageUrl,
          goal: 'conversion'
        })
      }, token);
      
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success') {
            setIntelligence(data.intelligence);
            setVeoPrompt(data.veo_prompt);
            setJsonPayload(data.json2video_payload);
            showToast('AI Pipeline Completed! Intelligence & Payloads Generated! 🚀');
        } else {
            throw new Error(data.message || 'Generation failed');
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.message || 'Generation failed');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  const executeRender = async () => {
    if (!jsonPayload) return showToast('Please generate a campaign first', true);
    
    setRendering(true);
    try {
      const res = await authFetch(`${API_BASE}/video/render`, {
        method: 'POST',
        body: JSON.stringify({
          provider,
          payload: jsonPayload,
          prompt: veoPrompt
        })
      }, token);

      if (res.ok) {
        const data = await res.json();
        setJobId(data.mediaId);
        setProjectUrl(data.videoUrl);
        showToast(data.message || 'Video Rendering Started! 🎥');
      } else {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || errData.message || 'Video rendering failed');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setRendering(false);
    }
  };

  const copyPayload = () => {
    navigator.clipboard.writeText(JSON.stringify(jsonPayload, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const presetTemplates = [
    { label: 'Shoes Promo', name: 'Nike Air Max', url: 'https://nike.com', img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80' },
    { label: 'Tech Gadget', name: 'Smart Watch', url: 'https://apple.com', img: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80' },
  ];

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ marginBottom: '2.5rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Film color="var(--primary-color)" size={32} /> AI Video Studio & Pipeline
          </h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
            Generate hyper-optimized marketing campaigns using OpenRouter AI and render natively with <code style={{ color: 'var(--primary-color)' }}>json2video</code>.
          </p>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '2rem' }}>
          {/* API Config Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div className="glass-panel" style={{ padding: '2rem', height: 'fit-content' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem', fontSize: '1.15rem' }}>
                <Settings size={20} color="var(--primary-color)" /> Integration Config
              </h3>
              
              <div className="input-group">
                <label>Rendering Provider</label>
                <select value={provider} onChange={e => setProvider(e.target.value)} disabled>
                  <option value="json2video">json2video.com (Native)</option>
                  <option value="veo">Google Veo 3.1 (Waitlist)</option>
                </select>
              </div>
              
              <div className="input-group">
                <label>json2video API Key</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', padding: '0.5rem' }}>
                  <Key size={16} color="rgba(255,255,255,0.4)" />
                  <input 
                    type="password" 
                    value={apiKey} 
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="Enter your API key"
                    style={{ border: 'none', background: 'transparent', flex: 1, color: '#fff', outline: 'none' }}
                  />
                </div>
              </div>
              
              <button 
                className="btn btn-primary" 
                style={{ width: '100%', marginTop: '1rem', display: 'flex', justifyContent: 'center' }}
                onClick={saveConfig}
                disabled={configLoading}
              >
                {configLoading ? 'Saving...' : 'Save Configuration'}
              </button>
            </div>
            
            <div className="glass-panel" style={{ padding: '2rem', height: 'fit-content' }}>
                <h3 style={{ marginBottom: '1rem', fontSize: '1.15rem' }}>Presets</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {presetTemplates.map((t, i) => (
                    <button 
                      key={i} 
                      className="btn" 
                      style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', textAlign: 'left', fontSize: '0.9rem', cursor: 'pointer', padding: '0.75rem', borderRadius: '6px' }}
                      onClick={() => {
                        setProductName(t.name);
                        setProductUrl(t.url);
                        setImageUrl(t.img);
                      }}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
            </div>
          </div>
          
          {/* Main Pipeline Editor */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div className="glass-panel" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h2 style={{ margin: 0, fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={20} color="var(--primary-color)" /> Campaign Pipeline Inputs
                </h2>
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div className="input-group">
                      <label>Product Name</label>
                      <input 
                          type="text" 
                          placeholder="e.g. Nike Air Max" 
                          value={productName}
                          onChange={e => setProductName(e.target.value)}
                      />
                  </div>
                  <div className="input-group">
                      <label>Product URL (For Web Scraping)</label>
                      <input 
                          type="text" 
                          placeholder="https://..." 
                          value={productUrl}
                          onChange={e => setProductUrl(e.target.value)}
                      />
                  </div>
                  <div className="input-group">
                      <label>Image URL (For Vision Analysis)</label>
                      <input 
                          type="text" 
                          placeholder="https://..." 
                          value={imageUrl}
                          onChange={e => setImageUrl(e.target.value)}
                      />
                  </div>
              </div>
              
              <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
                <button 
                  className="btn btn-primary" 
                  onClick={generateCampaign} 
                  disabled={loading}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, justifyContent: 'center' }}
                >
                  {loading ? (
                    <><span className="spinner" style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Processing AI Pipeline...</>
                  ) : (
                    <><LayoutTemplate size={18} /> Run AI Pipeline (Scrape &rarr; Vision &rarr; Brain)</>
                  )}
                </button>
              </div>
            </div>
            
            {/* Results Section */}
            {(veoPrompt || jsonPayload || intelligence) && (
              <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
                <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(0,0,0,0.2)' }}>
                  <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Check size={18} color="#10b981" /> Pipeline Output
                  </h3>
                </div>
                
                <div style={{ padding: '2rem' }}>
                    {intelligence && (
                        <div style={{ marginBottom: '2rem' }}>
                            <h4 style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }}>Marketing Intelligence Extract</h4>
                            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '1rem', borderRadius: '8px', fontSize: '0.9rem', color: '#d1d5db', display: 'flex', gap: '2rem' }}>
                                <div>
                                    <strong>Brand Vibe:</strong> {intelligence.brand_identity?.tone?.join(", ") || "Professional"}
                                </div>
                                <div>
                                    <strong>Target Audience:</strong> {intelligence.audience?.primary?.join(", ") || "General"}
                                </div>
                                <div>
                                    <strong>Hook:</strong> {intelligence.creative_strategy?.hero_marketing_hook || "Check this out"}
                                </div>
                            </div>
                        </div>
                    )}

                  <div style={{ marginBottom: '2rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem' }}>
                      Generated Veo 3.1 Prompt
                    </label>
                    <textarea 
                      className="glass-panel"
                      value={veoPrompt}
                      readOnly
                      style={{ width: '100%', minHeight: '120px', padding: '1rem', fontSize: '0.95rem', lineHeight: '1.6', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)' }}
                    />
                  </div>
                  
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '0.5rem' }}>
                      <label style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem' }}>
                        Generated <code style={{ color: 'var(--primary-color)' }}>json2video</code> API Payload
                      </label>
                      <button className="btn" style={{ padding: '0.4rem 0.75rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }} onClick={copyPayload}>
                        {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />} {copied ? 'Copied' : 'Copy JSON'}
                      </button>
                    </div>
                    
                    <pre style={{ margin: 0, padding: '1.5rem', background: '#0d0d0d', borderRadius: '8px', overflowX: 'auto', border: '1px solid rgba(255,255,255,0.05)', fontSize: '0.85rem', color: '#a78bfa' }}>
                      <code>{JSON.stringify(jsonPayload, null, 2)}</code>
                    </pre>
                  </div>
                </div>
                
                <div style={{ padding: '1.5rem 2rem', background: 'rgba(0,0,0,0.2)', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <button 
                    className="btn btn-primary" 
                    onClick={executeRender}
                    disabled={rendering}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '1rem', fontSize: '1.05rem', fontWeight: 600, background: 'linear-gradient(135deg, #10b981, #059669)' }}
                  >
                    {rendering ? (
                      <><span className="spinner" style={{ width: '18px', height: '18px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Submitting Render Job...</>
                    ) : (
                      <><Play size={20} fill="currentColor" /> Execute Video Render API</>
                    )}
                  </button>

                  {jobId && (
                      <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '8px', padding: '1rem', textAlign: 'center' }}>
                          <div style={{ color: '#10b981', fontWeight: 600, marginBottom: '0.5rem' }}>✅ Render Job Submitted Successfully</div>
                          <div style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.7)' }}>Job ID: {jobId}</div>
                          {projectUrl && (
                              <a href={projectUrl} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: '0.5rem', color: 'var(--primary-color)', textDecoration: 'none' }}>
                                  View Project Dashboard &rarr;
                              </a>
                          )}
                      </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}} />
    </div>
  );
};

export default VideoStudio;
