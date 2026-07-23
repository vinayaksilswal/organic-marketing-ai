import React, { useState } from 'react';
import { API_BASE, authFetch } from '../../App';
import { useWorkspace } from '../../components/WorkspaceContext';
import { Building2, Sparkles, Globe, Target, ArrowRight, Plus, CheckCircle2, ShieldCheck, Key, Settings } from 'lucide-react';

const Workspaces = ({ user, token, showToast, updateAuth }) => {
  const [isCreating, setIsCreating] = useState(false);
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [businessModel, setBusinessModel] = useState(null);
  const [loading, setLoading] = useState(false);
  const { activeWorkspaceId, setActiveWorkspace, refreshWorkspaces, workspaces } = useWorkspace();

  const businessList = workspaces && workspaces.length > 0 ? workspaces : (user?.businessProfiles || []);

  const handleProfileSubmit = async () => {
    if (!businessModel) {
      showToast('Please select a business model', true);
      return;
    }
    
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/businesses`, {
        method: 'POST',
        body: JSON.stringify({
          name: name || 'New Workspace',
          websiteUrl: website,
          description: description,
          businessModel: businessModel
        })
      }, token);

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.message || 'Failed to create workspace');
      }
      
      const resData = await res.json();
      const newProfile = resData.data || resData;

      if (updateAuth) {
        const updatedProfiles = [...businessList, newProfile];
        updateAuth({ ...user, businessProfiles: updatedProfiles });
      }

      refreshWorkspaces();
      if (newProfile?.id) setActiveWorkspace(newProfile.id);
      
      showToast('New Business Entity Created Successfully!');
      
      // Reset form
      setIsCreating(false);
      setStep(1);
      setName('');
      setWebsite('');
      setDescription('');
      setBusinessModel(null);
      
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2rem' }}>Businesses & Workspaces</h1>
            <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
              Manage multi-tenant brand entities, API keys, and enterprise workspace isolation.
            </p>
          </div>
          {!isCreating && (
            <button className="btn btn-primary" onClick={() => setIsCreating(true)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Plus size={18} /> Add Business Entity
            </button>
          )}
        </div>

        {!isCreating ? (
          <div className="media-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1.5rem' }}>
            {businessList.map(bp => {
              const isActive = activeWorkspaceId === bp.id;
              return (
                <div key={bp.id} className="glass-panel" style={{ 
                  padding: '2rem', 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '1.25rem',
                  border: isActive ? '1px solid var(--primary-color)' : '1px solid var(--border-color)',
                  position: 'relative',
                  background: isActive ? 'rgba(168, 85, 247, 0.05)' : 'var(--bg-card)'
                }}>
                  {isActive && (
                    <span style={{ 
                      position: 'absolute', 
                      top: '1rem', 
                      right: '1rem', 
                      background: 'var(--primary-color)', 
                      color: '#fff', 
                      fontSize: '0.7rem', 
                      fontWeight: '700', 
                      padding: '0.2rem 0.6rem', 
                      borderRadius: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.3rem'
                    }}>
                      <CheckCircle2 size={12} /> ACTIVE
                    </span>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ 
                      width: '52px', 
                      height: '52px', 
                      borderRadius: '14px', 
                      background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      fontWeight: 'bold', 
                      fontSize: '1.4rem',
                      color: '#fff',
                      boxShadow: '0 4px 14px rgba(168, 85, 247, 0.3)'
                    }}>
                      {bp.name ? bp.name.charAt(0).toUpperCase() : 'B'}
                    </div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '1.2rem' }}>{bp.name || 'My Business'}</h3>
                      <span className="badge" style={{ marginTop: '0.25rem', display: 'inline-block', fontSize: '0.75rem' }}>
                        {bp.businessModel || 'General'}
                      </span>
                    </div>
                  </div>

                  {bp.websiteUrl && (
                    <a href={bp.websiteUrl} target="_blank" rel="noreferrer" style={{ fontSize: '0.85rem', color: 'var(--secondary-color)', display: 'flex', alignItems: 'center', gap: '0.4rem', textDecoration: 'none' }}>
                      <Globe size={14} /> {bp.websiteUrl}
                    </a>
                  )}

                  <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', flex: 1, margin: 0, lineHeight: 1.5 }}>
                    {bp.description || 'No business description provided.'}
                  </p>

                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                    <button 
                      className={`btn ${isActive ? 'btn-primary' : 'btn-secondary'}`} 
                      style={{ flex: 1 }}
                      onClick={() => {
                        setActiveWorkspace(bp.id);
                        showToast(`Switched workspace to ${bp.name}`);
                      }}
                    >
                      {isActive ? 'Active Workspace' : 'Switch Workspace'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="glass-panel" style={{ maxWidth: '640px', padding: '3rem', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.5rem' }}>Onboard New Business Workspace</h2>
              <button className="btn btn-secondary" onClick={() => setIsCreating(false)}>Cancel</button>
            </div>
            
            <div className="wizard-progress" style={{ marginBottom: '2.5rem' }}>
              <div className={`wizard-step ${step >= 1 ? 'active' : ''}`}></div>
              <div className={`wizard-step ${step >= 2 ? 'active' : ''}`}></div>
            </div>

            {step === 1 && (
              <div className="fade-in">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <Building2 size={26} color="var(--primary-color)" />
                  <h3 style={{ margin: 0 }}>Business Identity</h3>
                </div>
                
                <div className="input-group">
                  <label>Business / Brand Name</label>
                  <input type="text" placeholder="e.g. Acme Innovations" value={name} onChange={e => setName(e.target.value)} />
                </div>
                
                <div className="input-group">
                  <label><Globe size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} /> Official Website URL</label>
                  <input type="url" placeholder="https://acme.com" value={website} onChange={e => setWebsite(e.target.value)} />
                </div>
                
                <div className="input-group">
                  <label><Target size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} /> Brand Voice & Description</label>
                  <textarea rows="4" placeholder="Describe products, services, value proposition, and target audience..." value={description} onChange={e => setDescription(e.target.value)}></textarea>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem' }}>
                  <button className="btn btn-primary btn-large" onClick={() => {
                    if(!name || !description) return showToast('Please enter business name and description', true);
                    setStep(2);
                  }}>
                    Continue <ArrowRight size={18} style={{ marginLeft: '0.5rem' }} />
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="fade-in">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <Sparkles size={26} color="var(--primary-color)" />
                  <h3 style={{ margin: 0 }}>Business Model & Category</h3>
                </div>
                <p style={{ marginBottom: '1.5rem', fontSize: '0.95rem', color: 'var(--text-muted)' }}>
                  This choice tunes the AI automation prompts, marketing schedules, and video generation layouts.
                </p>
                
                <div className="selection-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                  {[
                    { name: 'AI Influencer', icon: '🤖' },
                    { name: 'SaaS', icon: '💻' },
                    { name: 'E-commerce', icon: '🛒' },
                    { name: 'Creator', icon: '🎨' },
                    { name: 'Local Business', icon: '🏪' },
                    { name: 'Agency', icon: '🤝' }
                  ].map(model => (
                    <div 
                      key={model.name} 
                      className={`selection-card ${businessModel === model.name ? 'selected' : ''}`} 
                      onClick={() => setBusinessModel(model.name)}
                      style={{ padding: '1.25rem' }}
                    >
                      <span className="selection-card-icon" style={{ fontSize: '1.8rem', display: 'block', marginBottom: '0.5rem' }}>{model.icon}</span>
                      <strong style={{ fontSize: '1rem' }}>{model.name}</strong>
                    </div>
                  ))}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2.5rem' }}>
                  <button className="btn btn-secondary" onClick={() => setStep(1)}>Back</button>
                  <button className="btn btn-primary btn-large" onClick={handleProfileSubmit} disabled={loading}>
                    {loading ? <span className="spinner"></span> : 'Initialize Workspace'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Workspaces;

