import React, { useState } from 'react';
import { API_BASE, authFetch } from '../../config';
import { useWorkspace } from '../../components/WorkspaceContext';
import {
  Building2, Sparkles, Globe, Target, ArrowRight, Plus, CheckCircle2,
  Settings, X, Image, Link2, Facebook, Instagram, Linkedin, Twitter,
  Save, Edit3, ChevronRight, Zap, Clock, Bot
} from 'lucide-react';

const Workspaces = ({ user, token, showToast, updateAuth }) => {
  const [isCreating, setIsCreating] = useState(false);
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [businessModel, setBusinessModel] = useState(null);
  const [productCatalogUrl, setProductCatalogUrl] = useState('');
  const [influencerReferenceUrl, setInfluencerReferenceUrl] = useState('');
  const [loading, setLoading] = useState(false);

  // Edit modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTab, setEditTab] = useState('profile');
  const [editData, setEditData] = useState({});
  const [editWorkspaceId, setEditWorkspaceId] = useState(null);
  const [saving, setSaving] = useState(false);

  // Social connection fields
  const [socialData, setSocialData] = useState({
    fbAccessToken: '', fbPageId: '', fbPageName: '',
    igAccountId: '', igAccountName: '',
    linkedinAccessToken: '', twitterAccessToken: '', twitterAccessSecret: ''
  });

  const { activeWorkspaceId, setActiveWorkspace, refreshWorkspaces, workspaces } = useWorkspace();
  const businessList = workspaces && workspaces.length > 0 ? workspaces : (user?.businessProfiles || []);

  const handleProfileSubmit = async () => {
    if (!businessModel) return showToast('Please select a business model', true);
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/businesses`, {
        method: 'POST',
        body: JSON.stringify({ name: name || 'New Workspace', websiteUrl: website, description, businessModel, productCatalogUrl, influencerReferenceUrl })
      }, token);
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.message || 'Failed to create workspace');
      }
      const resData = await res.json();
      const newProfile = resData.data || resData;
      if (updateAuth) updateAuth({ ...user, businessProfiles: [...businessList, newProfile] });
      refreshWorkspaces();
      if (newProfile?.id) setActiveWorkspace(newProfile.id);
      showToast('Business created! AI is analyzing your brand and generating creatives...');
      setIsCreating(false); setStep(1); setName(''); setWebsite(''); setDescription('');
      setBusinessModel(null); setProductCatalogUrl(''); setInfluencerReferenceUrl('');
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  const openEditModal = (bp) => {
    setEditWorkspaceId(bp.id);
    setEditData({
      name: bp.name || '', websiteUrl: bp.websiteUrl || '', description: bp.description || '',
      businessModel: bp.businessModel || '', logoUrl: bp.logoUrl || '',
      productCatalogUrl: bp.productCatalogUrl || '', influencerReferenceUrl: bp.influencerReferenceUrl || '',
      postIntervalHours: bp.postIntervalHours || 2,
      creativeGenerationIntervalHours: bp.creativeGenerationIntervalHours || 12,
      autoGenerateCreatives: bp.autoGenerateCreatives !== false,
    });
    const sc = bp.socialConnection || {};
    setSocialData({
      fbAccessToken: '', fbPageId: sc.fbPageId || '', fbPageName: sc.fbPageName || '',
      igAccountId: sc.igAccountId || '', igAccountName: sc.igAccountName || '',
      linkedinAccessToken: '', twitterAccessToken: '', twitterAccessSecret: ''
    });
    setEditTab('profile');
    setEditModalOpen(true);
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const res = await authFetch(`${API_BASE}/businesses/${editWorkspaceId}`, {
        method: 'PATCH',
        body: JSON.stringify(editData)
      }, token);
      if (!res.ok) throw new Error('Failed to save');
      showToast('Business profile updated');
      refreshWorkspaces();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSocial = async () => {
    setSaving(true);
    try {
      const payload = {};
      if (socialData.fbAccessToken) payload.fbAccessToken = socialData.fbAccessToken;
      if (socialData.fbPageId) payload.fbPageId = socialData.fbPageId;
      if (socialData.fbPageName) payload.fbPageName = socialData.fbPageName;
      if (socialData.igAccountId) payload.igAccountId = socialData.igAccountId;
      if (socialData.igAccountName) payload.igAccountName = socialData.igAccountName;
      if (socialData.linkedinAccessToken) payload.linkedinAccessToken = socialData.linkedinAccessToken;
      if (socialData.twitterAccessToken) payload.twitterAccessToken = socialData.twitterAccessToken;
      if (socialData.twitterAccessSecret) payload.twitterAccessSecret = socialData.twitterAccessSecret;

      const res = await authFetch(`${API_BASE}/users/me/social-connection`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': editWorkspaceId },
        body: JSON.stringify(payload)
      }, token);
      if (!res.ok) throw new Error('Failed to save social accounts');
      showToast('Social accounts connected! Automation will post here.');
      refreshWorkspaces();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSaving(false);
    }
  };

  const currentBp = businessList.find(b => b.id === editWorkspaceId);

  const inputStyle = { width: '100%', padding: '0.7rem 0.85rem', borderRadius: '8px', background: 'rgba(255,255,255,0.04)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', fontSize: '0.9rem', outline: 'none' };
  const labelStyle = { display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)', fontWeight: 500 };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2rem' }}>Businesses & Workspaces</h1>
            <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
              Each business has its own social accounts, media catalog, and AI automation.
            </p>
          </div>
          {!isCreating && (
            <button className="btn btn-primary" onClick={() => setIsCreating(true)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Plus size={18} /> Add Business
            </button>
          )}
        </div>

        {!isCreating ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1.5rem' }}>
            {businessList.map(bp => {
              const isActive = activeWorkspaceId === bp.id;
              const sc = bp.socialConnection;
              return (
                <div key={bp.id} className="glass-panel" style={{
                  padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1rem',
                  border: isActive ? '1px solid var(--primary-color)' : '1px solid var(--border-color)',
                  position: 'relative', background: isActive ? 'rgba(168, 85, 247, 0.05)' : 'var(--bg-card)'
                }}>
                  {isActive && (
                    <span style={{ position: 'absolute', top: '0.85rem', right: '0.85rem', background: 'var(--primary-color)', color: '#fff', fontSize: '0.65rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <CheckCircle2 size={10} /> ACTIVE
                    </span>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                    {bp.logoUrl ? (
                      <img src={bp.logoUrl} alt="" style={{ width: 48, height: 48, borderRadius: 12, objectFit: 'cover', border: '1px solid rgba(255,255,255,0.1)' }} />
                    ) : (
                      <div style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '1.2rem', color: '#fff' }}>
                        {bp.name ? bp.name.charAt(0).toUpperCase() : 'B'}
                      </div>
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h3 style={{ margin: 0, fontSize: '1.1rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{bp.name || 'My Business'}</h3>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                        <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '6px', background: 'rgba(139,92,246,0.15)', color: 'var(--primary-color)', fontWeight: 600 }}>
                          {bp.businessModel || 'General'}
                        </span>
                        {bp.brandAnalysisComplete && (
                          <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '6px', background: 'rgba(16,185,129,0.15)', color: '#10b981', fontWeight: 600 }}>
                            AI Ready
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {bp.websiteUrl && (
                    <a href={bp.websiteUrl} target="_blank" rel="noreferrer" style={{ fontSize: '0.8rem', color: 'var(--secondary-color)', display: 'flex', alignItems: 'center', gap: '0.35rem', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <Globe size={13} /> {bp.websiteUrl}
                    </a>
                  )}

                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', flex: 1, margin: 0, lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {bp.description || 'No description provided.'}
                  </p>

                  {/* Social accounts status */}
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {sc?.hasFacebook && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '6px', background: 'rgba(59,130,246,0.12)', color: '#60a5fa' }}><Facebook size={12} /> {sc.fbPageName || 'Connected'}</span>}
                    {sc?.igAccountId && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '6px', background: 'rgba(236,72,153,0.12)', color: '#f472b6' }}><Instagram size={12} /> {sc.igAccountName || 'Connected'}</span>}
                    {sc?.hasLinkedin && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '6px', background: 'rgba(59,130,246,0.12)', color: '#93c5fd' }}><Linkedin size={12} /></span>}
                    {sc?.hasTwitter && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '6px', background: 'rgba(255,255,255,0.08)', color: '#e5e7eb' }}><Twitter size={12} /></span>}
                    {!sc && <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.35)' }}>No social accounts linked</span>}
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                    <button className={`btn ${isActive ? 'btn-primary' : 'btn-secondary'}`} style={{ flex: 1, fontSize: '0.85rem', padding: '0.55rem' }}
                      onClick={() => { setActiveWorkspace(bp.id); showToast(`Switched to ${bp.name}`); }}>
                      {isActive ? 'Active' : 'Switch'}
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '0.55rem 0.85rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                      onClick={() => openEditModal(bp)}>
                      <Edit3 size={14} /> Edit
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* Create wizard - same as before */
          <div className="glass-panel" style={{ maxWidth: '640px', padding: '3rem', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.5rem' }}>Onboard New Business</h2>
              <button className="btn btn-secondary" onClick={() => setIsCreating(false)}>Cancel</button>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2.5rem' }}>
              <div style={{ flex: 1, height: 4, borderRadius: 2, background: step >= 1 ? 'var(--primary-color)' : 'rgba(255,255,255,0.1)' }} />
              <div style={{ flex: 1, height: 4, borderRadius: 2, background: step >= 2 ? 'var(--primary-color)' : 'rgba(255,255,255,0.1)' }} />
            </div>

            {step === 1 && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <Building2 size={24} color="var(--primary-color)" />
                  <h3 style={{ margin: 0 }}>Business Identity</h3>
                </div>
                <div className="input-group">
                  <label>Business / Brand Name</label>
                  <input type="text" placeholder="e.g. Acme Innovations" value={name} onChange={e => setName(e.target.value)} />
                </div>
                <div className="input-group">
                  <label>Official Website URL</label>
                  <input type="url" placeholder="https://acme.com" value={website} onChange={e => setWebsite(e.target.value)} />
                </div>
                <div className="input-group">
                  <label>Brand Voice & Description</label>
                  <textarea rows="4" placeholder="Describe products, services, value proposition, and target audience..." value={description} onChange={e => setDescription(e.target.value)} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem' }}>
                  <button className="btn btn-primary" onClick={() => {
                    if(!name || !description) return showToast('Please enter business name and description', true);
                    setStep(2);
                  }}>Continue <ArrowRight size={18} style={{ marginLeft: '0.5rem' }} /></button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
                  <Sparkles size={24} color="var(--primary-color)" />
                  <h3 style={{ margin: 0 }}>Business Model</h3>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem', marginBottom: '1.5rem' }}>
                  {[
                    { name: 'AI Influencer', icon: '🤖' }, { name: 'SaaS', icon: '💻' },
                    { name: 'E-commerce', icon: '🛒' }, { name: 'Creator', icon: '🎨' },
                    { name: 'Local Business', icon: '🏪' }, { name: 'Agency', icon: '🤝' }
                  ].map(m => (
                    <div key={m.name} className={`selection-card ${businessModel === m.name ? 'selected' : ''}`}
                      onClick={() => setBusinessModel(m.name)} style={{ padding: '1rem', cursor: 'pointer' }}>
                      <span style={{ fontSize: '1.5rem', display: 'block', marginBottom: '0.35rem' }}>{m.icon}</span>
                      <strong style={{ fontSize: '0.9rem' }}>{m.name}</strong>
                    </div>
                  ))}
                </div>

                {businessModel === 'E-commerce' && (
                  <div style={{ padding: '1rem', background: 'rgba(168,85,247,0.05)', borderRadius: '10px', border: '1px solid rgba(168,85,247,0.2)', marginBottom: '1rem' }}>
                    <label style={labelStyle}><Sparkles size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Catalog Link (CSV/XML)</label>
                    <input type="url" placeholder="https://yourstore.com/products.csv" value={productCatalogUrl} onChange={e => setProductCatalogUrl(e.target.value)} style={inputStyle} />
                  </div>
                )}
                {businessModel === 'AI Influencer' && (
                  <div style={{ padding: '1rem', background: 'rgba(59,130,246,0.05)', borderRadius: '10px', border: '1px solid rgba(59,130,246,0.2)', marginBottom: '1rem' }}>
                    <label style={labelStyle}><Target size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Character Reference Image URL</label>
                    <input type="url" placeholder="https://example.com/character.jpg" value={influencerReferenceUrl} onChange={e => setInfluencerReferenceUrl(e.target.value)} style={inputStyle} />
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem' }}>
                  <button className="btn btn-secondary" onClick={() => setStep(1)}>Back</button>
                  <button className="btn btn-primary" onClick={handleProfileSubmit} disabled={loading}>
                    {loading ? <span className="spinner" /> : 'Initialize Workspace'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* EDIT MODAL */}
        {editModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}
            onClick={e => { if (e.target === e.currentTarget) setEditModalOpen(false); }}>
            <div className="glass-panel" style={{ width: '100%', maxWidth: 680, maxHeight: '90vh', overflow: 'auto', padding: 0 }}>
              {/* Header */}
              <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 2 }}>
                <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Settings size={18} /> Edit: {currentBp?.name || 'Workspace'}
                </h3>
                <button onClick={() => setEditModalOpen(false)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: '0.25rem' }}><X size={20} /></button>
              </div>

              {/* Tabs */}
              <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.06)', padding: '0 1.5rem' }}>
                {[
                  { key: 'profile', label: 'Business Profile', icon: <Building2 size={14} /> },
                  { key: 'social', label: 'Social Accounts', icon: <Link2 size={14} /> },
                  { key: 'automation', label: 'Automation', icon: <Zap size={14} /> },
                ].map(tab => (
                  <button key={tab.key} onClick={() => setEditTab(tab.key)}
                    style={{ padding: '0.75rem 1rem', background: 'none', border: 'none', borderBottom: editTab === tab.key ? '2px solid var(--primary-color)' : '2px solid transparent', color: editTab === tab.key ? '#fff' : 'rgba(255,255,255,0.5)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: editTab === tab.key ? 600 : 400 }}>
                    {tab.icon} {tab.label}
                  </button>
                ))}
              </div>

              <div style={{ padding: '1.5rem' }}>
                {/* PROFILE TAB */}
                {editTab === 'profile' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      <div>
                        <label style={labelStyle}>Business Name</label>
                        <input style={inputStyle} value={editData.name} onChange={e => setEditData({...editData, name: e.target.value})} />
                      </div>
                      <div>
                        <label style={labelStyle}>Business Model</label>
                        <select value={editData.businessModel} onChange={e => setEditData({...editData, businessModel: e.target.value})}
                          style={{ ...inputStyle, appearance: 'auto' }}>
                          {['SaaS', 'E-commerce', 'Creator', 'AI Influencer', 'Local Business', 'Agency', 'General'].map(m => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label style={labelStyle}>Website URL</label>
                      <input style={inputStyle} type="url" placeholder="https://..." value={editData.websiteUrl} onChange={e => setEditData({...editData, websiteUrl: e.target.value})} />
                    </div>

                    <div>
                      <label style={labelStyle}>Logo URL</label>
                      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                        {editData.logoUrl && <img src={editData.logoUrl} alt="" style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid rgba(255,255,255,0.1)' }} />}
                        <input style={{ ...inputStyle, flex: 1 }} type="url" placeholder="https://yourbrand.com/logo.png" value={editData.logoUrl} onChange={e => setEditData({...editData, logoUrl: e.target.value})} />
                      </div>
                    </div>

                    <div>
                      <label style={labelStyle}>Brand Description & Voice</label>
                      <textarea rows={3} style={{ ...inputStyle, resize: 'vertical' }} placeholder="Describe your brand, products, target audience..."
                        value={editData.description} onChange={e => setEditData({...editData, description: e.target.value})} />
                    </div>

                    {editData.businessModel === 'E-commerce' && (
                      <div>
                        <label style={labelStyle}><Sparkles size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Product Catalog URL (CSV/XML)</label>
                        <input style={inputStyle} type="url" placeholder="https://yourstore.com/products.csv" value={editData.productCatalogUrl} onChange={e => setEditData({...editData, productCatalogUrl: e.target.value})} />
                      </div>
                    )}

                    {editData.businessModel === 'AI Influencer' && (
                      <div>
                        <label style={labelStyle}><Target size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Influencer Character Reference URL</label>
                        <input style={inputStyle} type="url" placeholder="https://example.com/character.jpg" value={editData.influencerReferenceUrl} onChange={e => setEditData({...editData, influencerReferenceUrl: e.target.value})} />
                      </div>
                    )}

                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                      <button className="btn btn-primary" onClick={handleSaveProfile} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {saving ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Save size={15} />} Save Profile
                      </button>
                    </div>
                  </div>
                )}

                {/* SOCIAL ACCOUNTS TAB */}
                {editTab === 'social' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'rgba(255,255,255,0.5)' }}>
                      Connect social accounts for this workspace. The AI will auto-post creatives to these accounts.
                    </p>

                    {/* Facebook / Instagram */}
                    <div style={{ padding: '1.25rem', background: 'rgba(59,130,246,0.05)', borderRadius: '10px', border: '1px solid rgba(59,130,246,0.15)' }}>
                      <h4 style={{ margin: '0 0 1rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Facebook size={16} color="#60a5fa" /> Meta (Facebook & Instagram)
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                        <div>
                          <label style={labelStyle}>Page Access Token</label>
                          <input style={inputStyle} type="password" placeholder={currentBp?.socialConnection?.hasFacebook ? '••••••• (connected)' : 'Paste token...'} value={socialData.fbAccessToken} onChange={e => setSocialData({...socialData, fbAccessToken: e.target.value})} />
                        </div>
                        <div>
                          <label style={labelStyle}>Facebook Page ID</label>
                          <input style={inputStyle} placeholder="e.g. 123456789" value={socialData.fbPageId} onChange={e => setSocialData({...socialData, fbPageId: e.target.value})} />
                        </div>
                        <div>
                          <label style={labelStyle}>Page Name</label>
                          <input style={inputStyle} placeholder="Your Brand Page" value={socialData.fbPageName} onChange={e => setSocialData({...socialData, fbPageName: e.target.value})} />
                        </div>
                        <div>
                          <label style={labelStyle}>Instagram Account ID</label>
                          <input style={inputStyle} placeholder="IG Business Account ID" value={socialData.igAccountId} onChange={e => setSocialData({...socialData, igAccountId: e.target.value})} />
                        </div>
                      </div>
                      <div style={{ marginTop: '0.75rem' }}>
                        <label style={labelStyle}>Instagram Account Name</label>
                        <input style={inputStyle} placeholder="@yourbrand" value={socialData.igAccountName} onChange={e => setSocialData({...socialData, igAccountName: e.target.value})} />
                      </div>
                    </div>

                    {/* LinkedIn */}
                    <div style={{ padding: '1.25rem', background: 'rgba(59,130,246,0.03)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Linkedin size={16} color="#93c5fd" /> LinkedIn
                      </h4>
                      <label style={labelStyle}>Access Token</label>
                      <input style={inputStyle} type="password" placeholder={currentBp?.socialConnection?.hasLinkedin ? '••••••• (connected)' : 'Paste token...'} value={socialData.linkedinAccessToken} onChange={e => setSocialData({...socialData, linkedinAccessToken: e.target.value})} />
                    </div>

                    {/* Twitter */}
                    <div style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.02)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
                      <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Twitter size={16} color="#e5e7eb" /> Twitter / X
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                        <div>
                          <label style={labelStyle}>Access Token</label>
                          <input style={inputStyle} type="password" placeholder={currentBp?.socialConnection?.hasTwitter ? '••••••• (connected)' : 'Paste token...'} value={socialData.twitterAccessToken} onChange={e => setSocialData({...socialData, twitterAccessToken: e.target.value})} />
                        </div>
                        <div>
                          <label style={labelStyle}>Access Secret</label>
                          <input style={inputStyle} type="password" placeholder="Paste secret..." value={socialData.twitterAccessSecret} onChange={e => setSocialData({...socialData, twitterAccessSecret: e.target.value})} />
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <button className="btn btn-primary" onClick={handleSaveSocial} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {saving ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Link2 size={15} />} Save Social Accounts
                      </button>
                    </div>
                  </div>
                )}

                {/* AUTOMATION TAB */}
                {editTab === 'automation' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div>
                      <label style={labelStyle}><Clock size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Posting Frequency</label>
                      <select value={editData.postIntervalHours} onChange={e => setEditData({...editData, postIntervalHours: Number(e.target.value)})}
                        style={{ ...inputStyle, appearance: 'auto' }}>
                        <option value={1}>Every 1 hour</option>
                        <option value={2}>Every 2 hours</option>
                        <option value={4}>Every 4 hours</option>
                        <option value={8}>Every 8 hours</option>
                        <option value={12}>Every 12 hours</option>
                        <option value={24}>Every 24 hours</option>
                      </select>
                      <small style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)' }}>How often the AI publishes posts to your linked social accounts.</small>
                    </div>

                    <div>
                      <label style={labelStyle}><Bot size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Auto-Generate Creatives</label>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                        <input type="checkbox" checked={editData.autoGenerateCreatives} onChange={e => setEditData({...editData, autoGenerateCreatives: e.target.checked})} style={{ width: 18, height: 18 }} />
                        <span style={{ fontSize: '0.9rem' }}>Enable AI continuous creative generation</span>
                      </div>
                    </div>

                    {editData.autoGenerateCreatives && (
                      <div>
                        <label style={labelStyle}><Zap size={13} style={{ verticalAlign: 'middle', marginRight: '0.3rem' }} /> Creative Batch Interval</label>
                        <select value={editData.creativeGenerationIntervalHours} onChange={e => setEditData({...editData, creativeGenerationIntervalHours: Number(e.target.value)})}
                          style={{ ...inputStyle, appearance: 'auto' }}>
                          <option value={2}>Every 2 hours (Enterprise)</option>
                          <option value={4}>Every 4 hours</option>
                          <option value={6}>Every 6 hours</option>
                          <option value={12}>Every 12 hours</option>
                          <option value={24}>Every 24 hours</option>
                        </select>
                        <small style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.78rem', color: 'var(--primary-color)' }}>Faster intervals consume more AI generation capacity.</small>
                      </div>
                    )}

                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                      <button className="btn btn-primary" onClick={handleSaveProfile} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {saving ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Save size={15} />} Save Automation
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Workspaces;
