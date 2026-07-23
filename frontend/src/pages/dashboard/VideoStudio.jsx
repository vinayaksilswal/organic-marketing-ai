import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { Settings, Play, Code, Copy, Sparkles, Check, Film, Key, Globe } from 'lucide-react';

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  const [provider, setProvider] = useState('json2video');
  const [apiKey, setApiKey] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [prompt, setPrompt] = useState('');
  const [resolution, setResolution] = useState('1080p');
  const [duration, setDuration] = useState(15);
  const [generatedPromptText, setGeneratedPromptText] = useState('');
  const [generatedJson, setGeneratedJson] = useState('');
  const [parsedPayload, setParsedPayload] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [renderedMediaUrl, setRenderedMediaUrl] = useState(null);

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
          setEndpoint(body.data.endpoint || '');
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
        body: JSON.stringify({ provider, apiKey, endpoint })
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

  const generatePromptPayload = async () => {
    if (!prompt.trim()) return showToast('Please describe your video concept or prompt', true);
    
    setLoading(true);
    setRenderedMediaUrl(null);
    try {
      const res = await authFetch(`${API_BASE}/video/generate-prompt`, {
        method: 'POST',
        body: JSON.stringify({ prompt, provider, resolution, duration })
      }, token);
      
      if (res.ok) {
        const data = await res.json();
        setGeneratedPromptText(data.prompt);
        setParsedPayload(data.json);
        setGeneratedJson(JSON.stringify(data.json, null, 2));
        showToast('Prompt & JSON Payload Generated!');
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
    if (!parsedPayload) return showToast('Please generate a payload first', true);
    
    setRendering(true);
    try {
      const res = await authFetch(`${API_BASE}/video/render`, {
        method: 'POST',
        body: JSON.stringify({
          provider,
          payload: parsedPayload,
          prompt: generatedPromptText || prompt
        })
      }, token);

      if (res.ok) {
        const data = await res.json();
        setRenderedMediaUrl(data.videoUrl);
        showToast('Video Rendered & Saved to Media Repository! 🎥');
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
    navigator.clipboard.writeText(generatedJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const presetTemplates = [
    { label: '🚀 Product Launch (15s)', text: 'Create a vibrant 15-second promo highlighting key product features with bold typography and fast-paced scene cuts.' },
    { label: '🔥 Flash Sale Reel (10s)', text: 'High energy 10-second flash sale announcement with glowing countdown text and dynamic transitions.' },
    { label: '💡 Explainer Scene (30s)', text: 'A 30-second clean product walkthrough video explaining how our SaaS platform solves workflow friction.' }
  ];

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ marginBottom: '2.5rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Film color="var(--primary-color)" size={32} /> AI Video Studio & Prompt Engineer
          </h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
            Configure native <code style={{ color: 'var(--primary-color)' }}>json2video</code> rendering or connect external third-party video APIs.
          </p>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '2rem' }}>
          {/* API Config Panel */}
          <div className="glass-panel" style={{ padding: '2rem', height: 'fit-content' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem', fontSize: '1.15rem' }}>
              <Settings size={20} color="var(--primary-color)" /> API Integration
            </h3>
            
            <div className="input-group">
              <label>Rendering Provider</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="json2video">json2video (Native Engine)</option>
                <option value="runway">RunwayML Gen-2</option>
                <option value="pika">Pika Labs API</option>
                <option value="custom">Custom External API Endpoint</option>
              </select>
            </div>
            
            <div className="input-group">
              <label><Key size={14} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} /> Provider API Key</label>
              <input 
                type="password" 
                placeholder="Enter Provider API Key..." 
                value={apiKey} 
                onChange={(e) => setApiKey(e.target.value)} 
              />
            </div>

            {provider === 'custom' && (
              <div className="input-group">
                <label><Globe size={14} style={{ verticalAlign: 'middle', marginRight: '0.4rem' }} /> Custom API Endpoint URL</label>
                <input 
                  type="url" 
                  placeholder="https://api.yourprovider.com/v1/render" 
                  value={endpoint} 
                  onChange={(e) => setEndpoint(e.target.value)} 
                />
              </div>
            )}
            
            <button className="btn btn-secondary" style={{ width: '100%', marginTop: '0.5rem' }} onClick={saveConfig} disabled={configLoading}>
              {configLoading ? <span className="spinner"></span> : 'Save API Settings'}
            </button>

            <div style={{ marginTop: '2rem', padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
                💡 <strong>Engine Tip:</strong> Native <code>json2video</code> allows full scene, text element, background music, and timing control.
              </p>
            </div>
          </div>
          
          {/* Prompt Engineer Panel */}
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={20} color="var(--primary-color)" /> Prompt & Payload Architect
              </h3>
            </div>
            
            <p className="text-muted" style={{ marginBottom: '1.5rem', fontSize: '0.95rem' }}>
              Select a template or describe your video concept. Our AI will build optimized text prompts and valid JSON scene graph payloads.
            </p>

            {/* Quick Templates */}
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
              {presetTemplates.map((t, idx) => (
                <button 
                  key={idx} 
                  className="btn btn-secondary" 
                  style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', borderRadius: '20px' }}
                  onClick={() => setPrompt(t.text)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            
            <div className="input-group">
              <textarea 
                rows="4" 
                placeholder="Describe video objective, scene elements, colors, text overlays, and call-to-action..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Resolution</label>
                <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
                  <option value="1080p">1080p Full HD (16:9)</option>
                  <option value="square">Square 1:1 (Instagram)</option>
                  <option value="vertical">Vertical 9:16 (TikTok / Reels)</option>
                </select>
              </div>

              <div className="input-group" style={{ marginBottom: 0 }}>
                <label>Duration (Seconds)</label>
                <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                  <option value={10}>10 Seconds (Fast Reel)</option>
                  <option value={15}>15 Seconds (Standard Ad)</option>
                  <option value={30}>30 Seconds (Explainer)</option>
                </select>
              </div>
            </div>
            
            <button className="btn btn-primary btn-large" style={{ width: '100%' }} onClick={generatePromptPayload} disabled={loading || !prompt}>
              {loading ? <span className="spinner"></span> : <><Sparkles size={18} style={{ marginRight: '0.5rem' }} /> Generate Prompt & JSON Structure</>}
            </button>
            
            {generatedJson && (
              <div className="fade-in" style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
                {generatedPromptText && (
                  <div style={{ marginBottom: '1.25rem', padding: '1rem', background: 'rgba(168, 85, 247, 0.1)', borderRadius: '8px', border: '1px solid rgba(168, 85, 247, 0.3)' }}>
                    <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: '600', color: 'var(--primary-color)' }}>ENHANCED AI PROMPT</p>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem' }}>{generatedPromptText}</p>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0, fontSize: '1rem' }}>
                    <Code size={18} color="var(--success)" /> Generated {provider.toUpperCase()} Payload
                  </h4>
                  <button className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem' }} onClick={copyPayload}>
                    {copied ? <Check size={14} color="var(--success)" /> : <Copy size={14} />} {copied ? 'Copied' : 'Copy JSON'}
                  </button>
                </div>

                <pre style={{ 
                  background: 'rgba(0,0,0,0.6)', 
                  padding: '1.25rem', 
                  borderRadius: '12px', 
                  border: '1px solid var(--border-color)',
                  overflowX: 'auto',
                  maxHeight: '320px',
                  fontSize: '0.85rem',
                  color: '#a7f3d0',
                  lineHeight: '1.5'
                }}>
                  {generatedJson}
                </pre>
                
                <button 
                  className="btn btn-primary btn-large" 
                  style={{ marginTop: '1.5rem', width: '100%', background: 'linear-gradient(135deg, #10b981, #059669)' }} 
                  onClick={executeRender}
                  disabled={rendering}
                >
                  {rendering ? <span className="spinner"></span> : <><Play size={18} style={{ marginRight: '0.5rem' }} /> Execute Video Render Pipeline</>}
                </button>

                {renderedMediaUrl && (
                  <div className="fade-in" style={{ marginTop: '1.5rem', textAlign: 'center' }}>
                    <p style={{ color: 'var(--success)', fontWeight: '600', marginBottom: '0.5rem' }}>Render Complete! Preview Output:</p>
                    <video controls autoPlay src={renderedMediaUrl} style={{ width: '100%', maxHeight: '300px', borderRadius: '12px', border: '1px solid var(--border-color)' }} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoStudio;

