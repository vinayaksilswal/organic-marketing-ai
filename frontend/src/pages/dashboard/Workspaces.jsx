import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../config';
import { useWorkspace } from '../../components/WorkspaceContext';
import { Building2, Sparkles, Globe, Target, ArrowRight, Plus, CheckCircle2, Settings, X, Link2, Facebook, Instagram, Linkedin, Twitter, Save, Edit3, Zap, Clock, Bot, Trash2, AlertTriangle, Unplug, Pause, Play } from 'lucide-react';

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

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);

  const [connectingMeta, setConnectingMeta] = useState(false);
  const [pageChoices, setPageChoices] = useState(null); // { token, pages, workspaceId }
  const [selectingPage, setSelectingPage] = useState(null);

  const { activeWorkspaceId, setActiveWorkspace, refreshWorkspaces, workspaces } = useWorkspace();
  const businessList = workspaces && workspaces.length > 0 ? workspaces : (user?.businessProfiles || []);

  // Surface the result of the Meta OAuth round-trip, then clean the URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const meta = params.get('meta');
    if (!meta) return;
    const message = params.get('message');

    if (meta === 'connected') {
      showToast(`Connected ${message || 'your Meta account'}. Automation will publish here.`);
      refreshWorkspaces();
    } else if (meta === 'select') {
      // The account owns several Pages — let the user pick which one this
      // business publishes as, rather than silently taking the first.
      const t = params.get('token');
      if (t) loadPageChoices(t);
    } else {
      showToast(message || 'Could not connect your Meta account.', true);
    }
    window.history.replaceState({}, '', window.location.pathname);
  }, []);

  const loadPageChoices = async (t) => {
    try {
      const res = await authFetch(`${API_BASE}/meta/pages?token=${encodeURIComponent(t)}`, {}, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Could not load your Pages.');
      setPageChoices({ token: t, pages: data.pages || [], workspaceId: data.workspaceId });
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const handleSelectPage = async (pageId) => {
    setSelectingPage(pageId);
    try {
      const res = await authFetch(`${API_BASE}/meta/select-page`, {
        method: 'POST',
        body: JSON.stringify({ token: pageChoices.token, page_id: pageId }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Could not save that Page.');

      const c = data.connected || {};
      showToast(
        c.instagramUsername
          ? `Connected ${c.name} + @${c.instagramUsername}.`
          : `Connected ${c.name}.`
      );
      setPageChoices(null);
      refreshWorkspaces();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSelectingPage(null);
    }
  };

  const handleConnectMeta = async (workspaceId) => {
    setConnectingMeta(true);
    try {
      const res = await authFetch(`${API_BASE}/meta/connect?workspace_id=${encodeURIComponent(workspaceId)}`, {}, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.authUrl) {
        throw new Error(data.detail || data.message || 'Meta connection is unavailable right now.');
      }
      window.location.href = data.authUrl;
    } catch (err) {
      showToast(err.message, true);
      setConnectingMeta(false);
    }
  };

  const handleDeleteBusiness = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const res = await authFetch(`${API_BASE}/businesses/${deleteTarget.id}`, { method: 'DELETE' }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Failed to delete business');

      showToast(data.message || `'${deleteTarget.name}' deleted.`);
      if (activeWorkspaceId === deleteTarget.id) setActiveWorkspace(null);
      setDeleteTarget(null);
      setDeleteConfirmText('');
      setEditModalOpen(false);
      refreshWorkspaces();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setDeleting(false);
    }
  };

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

  // Pausing holds the automation without destroying anything. The
  // alternatives a user would otherwise reach for all lose something:
  // disconnecting the social account drops the token, deleting the workspace
  // drops the catalog, and a 24-hour interval still posts.
  const [pausing, setPausing] = useState(null);

  const toggleAutomation = async (bp) => {
    const next = !bp.automationPaused;
    setPausing(bp.id);
    try {
      const res = await authFetch(
        `${API_BASE}/businesses/${bp.id}`,
        { method: 'PATCH', body: JSON.stringify({ automationPaused: next }) },
        token
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showToast(next
        ? `${bp.name} paused — no posts until you resume`
        : `${bp.name} resumed — posting on its usual schedule`);
      await refreshWorkspaces();
    } catch (err) {
      showToast(`Could not ${next ? 'pause' : 'resume'} ${bp.name}`, 'error');
    } finally {
      setPausing(null);
    }
  };

  const openEditModal = (bp) => {
    setEditWorkspaceId(bp.id);
    setEditData({
      name: bp.name || '', websiteUrl: bp.websiteUrl || '', description: bp.description || '',
      businessModel: bp.businessModel || '', logoUrl: bp.logoUrl || '',
      productCatalogUrl: bp.productCatalogUrl || '', influencerReferenceUrl: bp.influencerReferenceUrl || '',
      primaryOffer: bp.primaryOffer || '',
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

  const inputStyle = { width: '100%', padding: '0.7rem 0.85rem', borderRadius: '8px', background: 'rgba(11, 16, 32, 0.04)', color: 'var(--text-main)', border: '1px solid var(--border-color)', fontSize: '0.9rem', outline: 'none' };
  const labelStyle = { display: 'block', marginBottom: '0.4rem', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 };

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

        {!isCreating && businessList.length === 0 ? (
          <div className="glass-panel" style={{ padding: '4rem 2rem', textAlign: 'center', maxWidth: 520, margin: '0 auto' }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, margin: '0 auto 1.5rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Building2 size={28} color="var(--primary-color)" />
            </div>
            <h2 style={{ margin: '0 0 0.6rem 0', fontSize: '1.35rem' }}>Add your first business</h2>
            <p style={{ margin: '0 0 1.75rem 0', fontSize: '0.92rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              Tell us your website and what you sell. The AI reads your site, learns your brand voice,
              and starts generating creatives and posts automatically.
            </p>
            <button className="btn btn-primary" onClick={() => setIsCreating(true)} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1.5rem' }}>
              <Plus size={18} /> Add Business
            </button>
          </div>
        ) : !isCreating ? (
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
                      <img src={bp.logoUrl} alt="" style={{ width: 48, height: 48, borderRadius: 12, objectFit: 'cover', border: '1px solid var(--border-color)' }} />
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
                    {sc?.hasTwitter && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '6px', background: 'rgba(11, 16, 32, 0.08)', color: '#e5e7eb' }}><Twitter size={12} /></span>}
                    {!sc?.hasFacebook && (
                      <button
                        onClick={() => handleConnectMeta(bp.id)}
                        disabled={connectingMeta}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', padding: '0.25rem 0.6rem', borderRadius: '6px', background: 'rgba(24,119,242,0.15)', border: '1px solid rgba(24,119,242,0.35)', color: '#60a5fa', cursor: 'pointer', fontWeight: 600 }}
                      >
                        <Facebook size={12} /> Connect
                      </button>
                    )}
                  </div>

                  {bp.automationPaused && (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '0.4rem',
                      fontSize: '0.75rem', padding: '0.3rem 0.6rem', borderRadius: 6,
                      background: 'rgba(234,179,8,0.12)', color: '#facc15',
                      border: '1px solid rgba(234,179,8,0.3)',
                    }}>
                      <Pause size={12} /> Automation paused — nothing is being posted
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                    <button className={`btn ${isActive ? 'btn-primary' : 'btn-secondary'}`} style={{ flex: 1, fontSize: '0.85rem', padding: '0.55rem' }}
                      onClick={() => { setActiveWorkspace(bp.id); showToast(`Switched to ${bp.name}`); }}>
                      {isActive ? 'Active' : 'Switch'}
                    </button>
                    <button
                      className="btn btn-secondary"
                      title={bp.automationPaused
                        ? 'Resume automatic posting for this business'
                        : 'Hold all automatic posting for this business'}
                      style={{
                        padding: '0.55rem 0.85rem', fontSize: '0.85rem',
                        display: 'flex', alignItems: 'center', gap: '0.35rem',
                        color: bp.automationPaused ? '#4ade80' : '#facc15',
                      }}
                      disabled={pausing === bp.id}
                      onClick={() => toggleAutomation(bp)}>
                      {pausing === bp.id
                        ? <span className="spinner" style={{ width: 14, height: 14 }} />
                        : bp.automationPaused ? <Play size={14} /> : <Pause size={14} />}
                      {bp.automationPaused ? 'Resume' : 'Pause'}
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
                    { name: 'Local Business', icon: '🏪' }, { name: 'Agency', icon: '🤝' },
                    /* A page IS the product: no thing to sell, the audience is
                       the asset. Creator is a person building a personal brand;
                       this is a themed account where the operator never
                       appears. They need different creative entirely. */
                    { name: 'Social Page', icon: '📱' }
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
              <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid rgba(11, 16, 32, 0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 2 }}>
                <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Settings size={18} /> Edit: {currentBp?.name || 'Workspace'}
                </h3>
                <button onClick={() => setEditModalOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer', padding: '0.25rem' }}><X size={20} /></button>
              </div>

              {/* Tabs */}
              <div style={{ display: 'flex', borderBottom: '1px solid rgba(11, 16, 32, 0.06)', padding: '0 1.5rem' }}>
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
                          {['SaaS', 'E-commerce', 'Creator', 'AI Influencer', 'Social Page', 'Local Business', 'Agency', 'General'].map(m => (
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
                        {editData.logoUrl && <img src={editData.logoUrl} alt="" style={{ width: 40, height: 40, borderRadius: 8, objectFit: 'cover', border: '1px solid var(--border-color)' }} />}
                        <input style={{ ...inputStyle, flex: 1 }} type="url" placeholder="https://yourbrand.com/logo.png" value={editData.logoUrl} onChange={e => setEditData({...editData, logoUrl: e.target.value})} />
                      </div>
                    </div>

                    <div>
                      <label style={labelStyle}>Brand Description & Voice</label>
                      <textarea rows={3} style={{ ...inputStyle, resize: 'vertical' }} placeholder="Describe your brand, products, target audience..."
                        value={editData.description} onChange={e => setEditData({...editData, description: e.target.value})} />
                    </div>

                    <div>
                      <label style={labelStyle}>Primary Offer / Call to Action</label>
                      <input style={inputStyle} type="text" maxLength={120}
                        placeholder="Start free — no credit card required"
                        value={editData.primaryOffer}
                        onChange={e => setEditData({...editData, primaryOffer: e.target.value})} />
                      <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        The one action every post and video should drive. Used word for word as
                        the on-screen line in videos and the closing CTA in captions. Leave blank
                        and the AI keeps it soft rather than inventing an offer you'd have to honour.
                      </p>
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

                    {/* Danger zone */}
                    <div style={{ marginTop: '1.5rem', padding: '1.15rem', borderRadius: '10px', background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.2)' }}>
                      <h4 style={{ margin: '0 0 0.35rem 0', fontSize: '0.9rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <AlertTriangle size={15} /> Danger zone
                      </h4>
                      <p style={{ margin: '0 0 0.85rem 0', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        Deleting this business permanently removes its media library, generated creatives,
                        scheduled posts, campaigns, products, and social connections. This cannot be undone.
                      </p>
                      <button
                        onClick={() => { setDeleteTarget(currentBp); setDeleteConfirmText(''); }}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.9rem', borderRadius: '8px', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)', color: '#f87171', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
                      >
                        <Trash2 size={14} /> Delete this business
                      </button>
                    </div>
                  </div>
                )}

                {/* SOCIAL ACCOUNTS TAB */}
                {editTab === 'social' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      Connect social accounts for this workspace. The AI will auto-post creatives to these accounts.
                    </p>

                    {/* Facebook / Instagram — one-click OAuth */}
                    <div style={{ padding: '1.25rem', background: 'rgba(59,130,246,0.05)', borderRadius: '10px', border: '1px solid rgba(59,130,246,0.15)' }}>
                      <h4 style={{ margin: '0 0 0.35rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Facebook size={16} color="#60a5fa" /> Meta — Facebook &amp; Instagram
                      </h4>

                      {currentBp?.socialConnection?.hasFacebook ? (
                        <>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', margin: '0.85rem 0' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                              <CheckCircle2 size={14} color="#10b981" />
                              <Facebook size={13} color="#60a5fa" />
                              <span>{currentBp.socialConnection.fbPageName || 'Facebook Page'}</span>
                            </div>
                            {currentBp.socialConnection.igAccountId && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                                <CheckCircle2 size={14} color="#10b981" />
                                <Instagram size={13} color="#f472b6" />
                                <span>@{currentBp.socialConnection.igAccountName || 'instagram'}</span>
                              </div>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button className="btn btn-secondary" style={{ fontSize: '0.82rem', padding: '0.45rem 0.85rem' }}
                              onClick={() => handleConnectMeta(editWorkspaceId)} disabled={connectingMeta}>
                              Reconnect
                            </button>
                            <button className="btn btn-secondary" style={{ fontSize: '0.82rem', padding: '0.45rem 0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#f87171' }}
                              onClick={async () => {
                                try {
                                  const res = await authFetch(`${API_BASE}/meta/disconnect?workspace_id=${encodeURIComponent(editWorkspaceId)}`, { method: 'DELETE' }, token);
                                  if (!res.ok) throw new Error('Failed to disconnect');
                                  showToast('Meta account disconnected.');
                                  refreshWorkspaces();
                                } catch (err) { showToast(err.message, true); }
                              }}>
                              <Unplug size={13} /> Disconnect
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p style={{ margin: '0 0 0.9rem 0', fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                            Sign in with Facebook and we'll automatically find your Page and its linked
                            Instagram Business account. No tokens to copy.
                          </p>
                          <button
                            onClick={() => handleConnectMeta(editWorkspaceId)}
                            disabled={connectingMeta}
                            style={{
                              display: 'flex', alignItems: 'center', gap: '0.55rem', width: '100%',
                              justifyContent: 'center', padding: '0.7rem', borderRadius: '8px',
                              background: '#1877f2', color: '#fff', border: 'none', fontSize: '0.9rem',
                              fontWeight: 600, cursor: connectingMeta ? 'wait' : 'pointer',
                              opacity: connectingMeta ? 0.7 : 1,
                            }}
                          >
                            <Facebook size={17} />
                            {connectingMeta ? 'Redirecting to Facebook…' : 'Connect Facebook & Instagram'}
                          </button>
                        </>
                      )}
                    </div>

                    {/* LinkedIn */}
                    <div style={{ padding: '1.25rem', background: 'rgba(59,130,246,0.03)', borderRadius: '10px', border: '1px solid rgba(11, 16, 32, 0.06)' }}>
                      <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Linkedin size={16} color="#93c5fd" /> LinkedIn
                      </h4>
                      <label style={labelStyle}>Access Token</label>
                      <input style={inputStyle} type="password" placeholder={currentBp?.socialConnection?.hasLinkedin ? '••••••• (connected)' : 'Paste token...'} value={socialData.linkedinAccessToken} onChange={e => setSocialData({...socialData, linkedinAccessToken: e.target.value})} />
                    </div>

                    {/* Twitter */}
                    <div style={{ padding: '1.25rem', background: 'rgba(11, 16, 32, 0.02)', borderRadius: '10px', border: '1px solid rgba(11, 16, 32, 0.06)' }}>
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
                      <small style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>How often the AI publishes posts to your linked social accounts.</small>
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

        {/* META PAGE PICKER — shown when the account owns several Pages */}
        {pageChoices && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: '1rem' }}>
            <div className="glass-panel" style={{ width: '100%', maxWidth: 520, padding: '1.75rem', maxHeight: '85vh', overflow: 'auto' }}>
              <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Facebook size={18} color="#60a5fa" /> Choose a Page
              </h3>
              <p style={{ margin: '0 0 1.25rem 0', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
                Your Facebook account manages more than one Page. Pick the one this business
                should publish as — its linked Instagram account will be connected too.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {pageChoices.pages.map(p => (
                  <button
                    key={p.id}
                    onClick={() => handleSelectPage(p.id)}
                    disabled={!!selectingPage}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.75rem', width: '100%',
                      padding: '0.85rem 1rem', borderRadius: '10px', textAlign: 'left',
                      background: 'rgba(11, 16, 32, 0.03)', border: '1px solid var(--border-color)',
                      color: '#fff', cursor: selectingPage ? 'wait' : 'pointer',
                      opacity: selectingPage && selectingPage !== p.id ? 0.4 : 1,
                    }}
                  >
                    <Facebook size={17} color="#60a5fa" style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.92rem', fontWeight: 600 }}>{p.name}</div>
                      {p.instagramUsername ? (
                        <div style={{ fontSize: '0.78rem', color: '#f472b6', display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.15rem' }}>
                          <Instagram size={11} /> @{p.instagramUsername}
                        </div>
                      ) : (
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                          No Instagram Business account linked
                        </div>
                      )}
                    </div>
                    {selectingPage === p.id && <span className="spinner" style={{ width: 14, height: 14 }} />}
                  </button>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.35rem' }}>
                <button className="btn btn-secondary" onClick={() => setPageChoices(null)} disabled={!!selectingPage}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* DELETE CONFIRMATION */}
        {deleteTarget && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: '1rem' }}
            onClick={e => { if (e.target === e.currentTarget && !deleting) setDeleteTarget(null); }}>
            <div className="glass-panel" style={{ width: '100%', maxWidth: 460, padding: '1.75rem' }}>
              <h3 style={{ margin: '0 0 0.6rem 0', fontSize: '1.1rem', color: '#f87171', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={18} /> Delete “{deleteTarget.name}”?
              </h3>
              <p style={{ margin: '0 0 1.1rem 0', fontSize: '0.87rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                This permanently deletes the business and everything belonging to it — media library,
                generated creatives, scheduled and published posts, campaigns, products, and connected
                social accounts. This cannot be undone.
              </p>

              <label style={{ ...labelStyle, marginBottom: '0.4rem' }}>
                Type <strong style={{ color: '#f87171' }}>{deleteTarget.name}</strong> to confirm
              </label>
              <input
                style={{ ...inputStyle, borderColor: 'rgba(239,68,68,0.3)' }}
                value={deleteConfirmText}
                onChange={e => setDeleteConfirmText(e.target.value)}
                placeholder={deleteTarget.name}
                autoFocus
              />

              <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'flex-end', marginTop: '1.35rem' }}>
                <button className="btn btn-secondary" onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</button>
                <button
                  onClick={handleDeleteBusiness}
                  disabled={deleting || deleteConfirmText !== deleteTarget.name}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 1.1rem',
                    borderRadius: '8px', border: 'none', fontSize: '0.88rem', fontWeight: 600,
                    background: deleteConfirmText === deleteTarget.name ? '#dc2626' : 'rgba(239,68,68,0.2)',
                    color: deleteConfirmText === deleteTarget.name ? '#fff' : 'rgba(255,255,255,0.35)',
                    cursor: deleteConfirmText === deleteTarget.name && !deleting ? 'pointer' : 'not-allowed',
                  }}
                >
                  {deleting ? <span className="spinner" style={{ width: 13, height: 13 }} /> : <Trash2 size={14} />}
                  {deleting ? 'Deleting…' : 'Delete permanently'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Workspaces;
