import React, { useState } from 'react';
import { UploadCloud, CheckCircle2, Facebook, Instagram, Twitter, Linkedin, Sparkles, BarChart3, Activity } from 'lucide-react';

const Dashboard = ({ user, showToast }) => {
  const [metaConnected, setMetaConnected] = useState(false);
  const [xConnected, setXConnected] = useState(false);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    const newFiles = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files).filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const startAutomation = () => {
    if (files.length === 0) return showToast('Please upload media first', true);
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setFiles([]);
      showToast('Campaign Generated! Marketing loop scheduled successfully.');
    }, 2000);
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
          <div>
            <h1>Command Center</h1>
            <p className="text-muted" style={{ fontSize: '1.125rem' }}>
              Welcome back. Your automation engine is <span className="badge active"><span className="status-dot green"></span>Active</span>
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ margin: 0, fontWeight: '600' }}>Pro Plan <span style={{ color: 'var(--primary-color)' }}>$17/mo</span></p>
            <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)' }}>{user?.email}</p>
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '3rem' }}>
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '1rem', borderRadius: '12px' }}>
              <Activity size={24} color="var(--primary-color)" />
            </div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--text-muted)', fontWeight: '500' }}>Posts Generated</h4>
              <h2 style={{ margin: 0 }}>124</h2>
            </div>
          </div>
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ background: 'rgba(59, 130, 246, 0.1)', padding: '1rem', borderRadius: '12px' }}>
              <BarChart3 size={24} color="var(--secondary-color)" />
            </div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--text-muted)', fontWeight: '500' }}>Total Reach</h4>
              <h2 style={{ margin: 0 }}>45.2k</h2>
            </div>
          </div>
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '1rem', borderRadius: '12px' }}>
              <Sparkles size={24} color="var(--success)" />
            </div>
            <div>
              <h4 style={{ margin: 0, color: 'var(--text-muted)', fontWeight: '500' }}>Conversion Est.</h4>
              <h2 style={{ margin: 0 }}>4.8%</h2>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
          {/* Integrations Column */}
          <div>
            <div className="glass-panel" style={{ padding: '2rem', marginBottom: '2rem' }}>
              <h3>Connected Platforms</h3>
              <p style={{ fontSize: '0.875rem', marginBottom: '2rem', color: 'var(--text-muted)' }}>Link your accounts to enable automated posting.</p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* Meta Integration */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: metaConnected ? '1rem' : '0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <Facebook size={20} color="#1877F2" />
                      <Instagram size={20} color="#E4405F" />
                      <span style={{ fontWeight: '600' }}>Meta</span>
                    </div>
                    {metaConnected ? (
                      <span className="badge active" style={{ fontSize: '0.65rem' }}>Connected</span>
                    ) : (
                      <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }} onClick={() => { setMetaConnected(true); showToast('Meta connected!'); }}>Connect</button>
                    )}
                  </div>
                  {metaConnected && (
                    <div className="fade-in">
                      <div className="input-group" style={{ marginBottom: '0.75rem' }}>
                        <select style={{ padding: '0.5rem', fontSize: '0.875rem' }}><option>My Business Page</option></select>
                      </div>
                      <div className="input-group" style={{ marginBottom: '0' }}>
                        <select style={{ padding: '0.5rem', fontSize: '0.875rem' }}><option>@mybusiness_ig</option></select>
                      </div>
                    </div>
                  )}
                </div>

                {/* X Integration */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <Twitter size={20} color="#1DA1F2" />
                      <span style={{ fontWeight: '600' }}>X (Twitter)</span>
                    </div>
                    {xConnected ? (
                      <span className="badge active" style={{ fontSize: '0.65rem' }}>Connected</span>
                    ) : (
                      <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }} onClick={() => { setXConnected(true); showToast('X connected!'); }}>Connect</button>
                    )}
                  </div>
                </div>

                {/* LinkedIn Integration */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <Linkedin size={20} color="#0A66C2" />
                      <span style={{ fontWeight: '600' }}>LinkedIn</span>
                    </div>
                    <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}>Connect</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Campaign Generator Column */}
          <div>
            <div className="glass-panel" style={{ padding: '2.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
                <div>
                  <h3>AI Campaign Generator</h3>
                  <p style={{ color: 'var(--text-muted)' }}>Upload raw media. Our AI will analyze it, write platform-specific copy, and schedule the posts.</p>
                </div>
                <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '0.5rem 1rem', borderRadius: '999px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Sparkles size={16} color="var(--primary-color)" />
                  <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--primary-color)' }}>Context: {user?.businessProfile?.businessModel || 'AI Tuned'}</span>
                </div>
              </div>
              
              <div 
                className="dropzone" 
                onDragOver={e => e.preventDefault()} 
                onDrop={handleDrop}
                onClick={() => document.getElementById('file-input').click()}
              >
                <UploadCloud className="dropzone-icon" />
                <h4>Drag & Drop media here</h4>
                <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>Supports Images & Videos (Max 50MB)</p>
                <input type="file" id="file-input" multiple accept="image/*,video/*" className="hidden" onChange={handleFileChange} />
              </div>

              {files.length > 0 && (
                <div className="media-grid fade-in">
                  {files.map((file, i) => (
                    <div key={i} className="media-item">
                      {file.type.startsWith('image/') ? 
                        <img src={URL.createObjectURL(file)} alt="preview" /> : 
                        <video src={URL.createObjectURL(file)} />
                      }
                      <button style={{ position: 'absolute', top: '0.25rem', right: '0.25rem', background: 'rgba(0,0,0,0.5)', border: 'none', color: 'white', borderRadius: '50%', width: '24px', height: '24px', cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); setFiles(files.filter((_, idx) => idx !== i)); }}>&times;</button>
                    </div>
                  ))}
                </div>
              )}

              <button className="btn btn-primary btn-large" style={{ width: '100%' }} onClick={startAutomation} disabled={loading}>
                <span className="btn-text">Generate & Schedule Campaign</span>
                {loading && <span className="spinner"></span>}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
