import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { Sparkles, Check, Film, LayoutTemplate } from 'lucide-react';

const VideoStudio = ({ user, token, showToast, activeWorkspaceId }) => {
  // Pipeline inputs
  const [productName, setProductName] = useState('');
  const [productUrl, setProductUrl] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  
  // Outputs
  const [intelligence, setIntelligence] = useState(null);
  const [veoPrompt, setVeoPrompt] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef(null);

  useEffect(() => {
    //
  }, [activeWorkspaceId]);

  const generateCampaign = async () => {
    if (!productName || !imageUrl) {
      return showToast('Please provide Product Name and Image URL', true);
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
            showToast('AI Pipeline Completed! Intelligence & Prompts Generated! 🚀');
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
    // Removed
  };

  const copyPayload = () => {
    // Removed
  };

  const presetTemplates = [
    { label: 'Shoes Promo', name: 'Nike Air Max', url: 'https://nike.com', img: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=80' },
    { label: 'Tech Gadget', name: 'Smart Watch', url: 'https://apple.com', img: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80' },
  ];

  const handleManualUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/upload-media`, {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Workspace-Id': activeWorkspaceId || ''
        }
      });
      if (res.ok) {
        showToast('Video uploaded to Media Catalog successfully!');
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || 'Upload failed');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ marginBottom: '2.5rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Film color="var(--primary-color)" size={32} /> AI Video Studio
          </h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
            Generate hyper-optimized marketing video prompts using OpenRouter AI.
          </p>
        </div>
        
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '2rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            
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
                  <Sparkles size={20} color="var(--primary-color)" /> Campaign Inputs
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
                    <><span className="spinner" style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Processing Prompt...</>
                  ) : (
                    <><LayoutTemplate size={18} /> Generate Video Prompt</>
                  )}
                </button>
              </div>
            </div>
            
            {/* Results Section */}
            {(veoPrompt || jsonPayload || intelligence) && (
              <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
                <div style={{ padding: '1.5rem 2rem', borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(0,0,0,0.2)' }}>
                  <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Check size={18} color="#10b981" /> Generated Results
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '0.5rem' }}>
                      <label style={{ display: 'block', color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem' }}>
                        Generated AI Video Prompt
                      </label>
                    </div>
                    <textarea 
                      className="glass-panel"
                      value={veoPrompt}
                      readOnly
                      style={{ width: '100%', minHeight: '120px', padding: '1rem', fontSize: '0.95rem', lineHeight: '1.6', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.05)', marginBottom: '1rem' }}
                    />
                    
                    <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.1)', padding: '1rem', borderRadius: '8px' }}>
                      <h5 style={{ margin: '0 0 0.5rem 0', color: '#e5e7eb', fontSize: '0.95rem' }}>Upload Video</h5>
                      <p style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: 'rgba(255,255,255,0.6)' }}>
                        Use the prompt above in tools like Google Veo, Runway, or Midjourney. Then upload the resulting video here for use in automation.
                      </p>
                      <input 
                        type="file" 
                        accept="video/*" 
                        ref={fileInputRef} 
                        onChange={handleManualUpload} 
                        style={{ display: 'none' }} 
                      />
                      <button 
                        className="btn" 
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.1)', border: 'none', padding: '0.5rem 1rem' }}
                      >
                        {uploading ? (
                          <><span className="spinner" style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Uploading...</>
                        ) : (
                          <><Check size={16} /> Upload Video to Media</>
                        )}
                      </button>
                    </div>
                  </div>
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
