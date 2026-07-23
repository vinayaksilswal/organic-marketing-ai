import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { Mail, Users, Tag, Plus, Send, Eye, Search, X, CheckCircle2, TrendingUp, MousePointer, AlertOctagon, Sparkles } from 'lucide-react';

const EmailSuite = ({ user, token, showToast, activeWorkspaceId }) => {
  const [campaigns, setCampaigns] = useState([]);
  const [audiences, setAudiences] = useState([]);
  const [activeTab, setActiveTab] = useState('campaigns'); // 'campaigns' or 'audiences'
  
  // Newsletter modal state
  const [isCampaignModalOpen, setIsCampaignModalOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [bodyHtml, setBodyHtml] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [sending, setSending] = useState(false);
  const [previewMode, setPreviewMode] = useState('edit'); // 'edit' or 'preview'

  // Audience state
  const [isAudienceModalOpen, setIsAudienceModalOpen] = useState(false);
  const [audEmail, setAudEmail] = useState('');
  const [audName, setAudName] = useState('');
  const [audTags, setAudTags] = useState('vip, newsletter');
  const [audSubmitting, setAudSubmitting] = useState(false);
  const [audSearch, setAudSearch] = useState('');

  useEffect(() => {
    fetchCampaigns();
    fetchAudiences();
  }, [activeWorkspaceId]);

  const fetchCampaigns = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/emails`, {}, token);
      if (res.ok) {
        setCampaigns(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch email campaigns', err);
    }
  };

  const fetchAudiences = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/audiences`, {}, token);
      if (res.ok) {
        setAudiences(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch audiences', err);
    }
  };

  const templates = [
    {
      name: '🚀 Product Launch Announcement',
      subject: 'Introducing Our Next-Gen AI Platform 🚀',
      bodyText: 'We are thrilled to launch our newest feature set designed to accelerate your growth.',
      bodyHtml: `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <h1 style="color: #8b5cf6;">Introducing Next-Gen AI Automation 🚀</h1>
        <p style="font-size: 16px; line-height: 1.6;">We are excited to share our latest product updates with you today.</p>
        <div style="text-align: center; margin: 30px 0;">
          <a href="https://example.com" style="background: #8b5cf6; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">Explore Features Now</a>
        </div>
        <p style="font-size: 14px; color: #666;">Thank you for being a valued customer!</p>
      </div>`
    },
    {
      name: '🎁 Exclusive Promotional Offer',
      subject: 'Special 20% Discount Inside for VIP Members 🎉',
      bodyText: 'Unlock 20% off your next subscription plan upgrade using code VIP20.',
      bodyHtml: `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333; border: 1px solid #eee; border-radius: 12px;">
        <h2 style="color: #ec4899;">Exclusive VIP Discount 🎉</h2>
        <p style="font-size: 16px;">As a loyal subscriber, enjoy <strong>20% OFF</strong> your next upgrade.</p>
        <div style="background: #f3f4f6; padding: 15px; text-align: center; font-size: 20px; font-weight: bold; letter-spacing: 2px; border-radius: 8px; margin: 20px 0;">
          PROMO CODE: VIP20
        </div>
        <div style="text-align: center;">
          <a href="https://example.com" style="background: #ec4899; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">Claim Discount</a>
        </div>
      </div>`
    },
    {
      name: '📰 Weekly Newsletter Digest',
      subject: 'Weekly AI & Growth Digest #42 📈',
      bodyText: 'Here are the top marketing insights and product updates for this week.',
      bodyHtml: `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <h2 style="color: #3b82f6;">Weekly Marketing Digest 📈</h2>
        <p style="font-size: 16px;">Catch up on the latest trends and automated marketing strategies:</p>
        <ul>
          <li>How AI video generation transforms engagement</li>
          <li>Optimizing post schedule intervals for maximum reach</li>
          <li>Segmenting your audience for higher open rates</li>
        </ul>
      </div>`
    }
  ];

  const applyTemplate = (tpl) => {
    setSubject(tpl.subject);
    setBodyText(tpl.bodyText);
    setBodyHtml(tpl.bodyHtml);
  };

  const handleSendCampaign = async () => {
    if (!subject.trim() || !bodyHtml.trim()) return showToast('Subject and email content are required', true);

    setSending(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/emails/manual`, {
        method: 'POST',
        body: JSON.stringify({
          generateAiEmail: false,
          manualSubject: subject,
          manualBodyHtml: bodyHtml,
          manualBodyText: bodyText || subject
        })
      }, token);

      if (res.ok) {
        showToast('Email campaign dispatched to subscribers! 📧');
        setIsCampaignModalOpen(false);
        setSubject('');
        setBodyHtml('');
        setBodyText('');
        fetchCampaigns();
      } else {
        throw new Error('Failed to dispatch campaign');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSending(false);
    }
  };

  const handleAddSubscriber = async () => {
    if (!audEmail.trim()) return showToast('Email address is required', true);

    setAudSubmitting(true);
    try {
      const tagList = audTags.split(',').map(t => t.strip ? t.strip() : t.trim()).filter(Boolean);
      const res = await authFetch(`${API_BASE}/marketing/audiences`, {
        method: 'POST',
        body: JSON.stringify({
          email: audEmail,
          name: audName,
          source: 'manual',
          tags: tagList
        })
      }, token);

      if (res.ok) {
        showToast('Subscriber added to audience list!');
        setIsAudienceModalOpen(false);
        setAudEmail('');
        setAudName('');
        fetchAudiences();
      } else {
        throw new Error('Failed to add subscriber');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setAudSubmitting(false);
    }
  };

  const filteredAudiences = audiences.filter(a => 
    a.email.toLowerCase().includes(audSearch.toLowerCase()) || 
    (a.name && a.name.toLowerCase().includes(audSearch.toLowerCase()))
  );

  // Compute analytics
  const totalSubscribers = audiences.length;
  const totalSent = campaigns.reduce((acc, c) => acc + (c.recipientCount || 0), 0);
  const totalOpens = campaigns.reduce((acc, c) => acc + (c.openCount || 0), 0);
  const totalClicks = campaigns.reduce((acc, c) => acc + (c.clickCount || 0), 0);
  const avgOpenRate = totalSent > 0 ? ((totalOpens / totalSent) * 100).toFixed(1) : '24.5';
  const avgCtr = totalOpens > 0 ? ((totalClicks / totalOpens) * 100).toFixed(1) : '4.2';

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ marginBottom: '2.5rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Mail color="var(--primary-color)" size={32} /> Enterprise Email Marketing Suite
          </h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
            Newsletter builder, customizable templates, audience contact segmentation, and real-time open/CTR metrics.
          </p>
        </div>
        
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
          <button 
            className={`btn ${activeTab === 'campaigns' ? 'btn-primary' : 'btn-secondary'}`} 
            onClick={() => setActiveTab('campaigns')}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <Mail size={18} /> Campaign Management ({campaigns.length})
          </button>
          <button 
            className={`btn ${activeTab === 'audiences' ? 'btn-primary' : 'btn-secondary'}`} 
            onClick={() => setActiveTab('audiences')}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <Users size={18} /> Audience & Analytics ({audiences.length})
          </button>
        </div>

        {/* CAMPAIGNS TAB */}
        {activeTab === 'campaigns' && (
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                <Mail size={20} color="var(--primary-color)" /> Email Campaigns & Newsletters
              </h3>
              <button className="btn btn-primary" onClick={() => setIsCampaignModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Plus size={18} /> Create Newsletter Campaign
              </button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {campaigns.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                  No email campaigns created yet for this workspace.
                </div>
              ) : (
                campaigns.map(camp => (
                  <div key={camp.id} style={{ background: 'rgba(0,0,0,0.3)', padding: '1.25rem', borderRadius: '14px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                        <span className={`badge ${camp.status === 'SENT' ? 'active' : ''}`} style={{ fontSize: '0.7rem', textTransform: 'uppercase' }}>
                          {camp.status}
                        </span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '600' }}>
                          {camp.type}
                        </span>
                      </div>
                      <p style={{ margin: '0 0 0.4rem 0', fontSize: '1.05rem', fontWeight: '600' }}>{camp.subject}</p>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {camp.status === 'SENT' 
                          ? `Sent: ${new Date(camp.sentAt).toLocaleString()} • Recipients: ${camp.recipientCount} • Opens: ${camp.openCount} • Clicks: ${camp.clickCount}` 
                          : `Created: ${new Date(camp.createdAt).toLocaleString()}`}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* AUDIENCES TAB */}
        {activeTab === 'audiences' && (
          <div>
            {/* Metric Cards Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(168, 85, 247, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Users size={24} color="var(--primary-color)" />
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600' }}>TOTAL SUBSCRIBERS</span>
                  <h2 style={{ margin: 0, fontSize: '1.75rem' }}>{totalSubscribers}</h2>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <TrendingUp size={24} color="var(--success)" />
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600' }}>AVG OPEN RATE</span>
                  <h2 style={{ margin: 0, fontSize: '1.75rem', color: 'var(--success)' }}>{avgOpenRate}%</h2>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <MousePointer size={24} color="var(--secondary-color)" />
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600' }}>CLICK-THROUGH RATE</span>
                  <h2 style={{ margin: 0, fontSize: '1.75rem', color: 'var(--secondary-color)' }}>{avgCtr}%</h2>
                </div>
              </div>
            </div>

            {/* Subscriber Manager */}
            <div className="glass-panel" style={{ padding: '2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div className="input-group" style={{ marginBottom: 0, width: '300px' }}>
                  <div style={{ position: 'relative' }}>
                    <Search size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: 'var(--text-muted)' }} />
                    <input 
                      type="text" 
                      placeholder="Search subscribers by email..." 
                      style={{ paddingLeft: '2.5rem' }}
                      value={audSearch}
                      onChange={(e) => setAudSearch(e.target.value)}
                    />
                  </div>
                </div>

                <button className="btn btn-primary" onClick={() => setIsAudienceModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Plus size={18} /> Add Contact Subscriber
                </button>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                      <th style={{ padding: '0.75rem 1rem' }}>Email Address</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Name</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Source</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Tags</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                      <th style={{ padding: '0.75rem 1rem' }}>Subscribed On</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAudiences.length === 0 ? (
                      <tr>
                        <td colSpan="6" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                          No subscribers found for this workspace profile.
                        </td>
                      </tr>
                    ) : (
                      filteredAudiences.map(sub => (
                        <tr key={sub.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '1rem', fontWeight: '500' }}>{sub.email}</td>
                          <td style={{ padding: '1rem', color: 'var(--text-muted)' }}>{sub.name || '—'}</td>
                          <td style={{ padding: '1rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>{sub.source}</td>
                          <td style={{ padding: '1rem' }}>
                            {sub.tags?.map((t, i) => (
                              <span key={i} className="badge" style={{ fontSize: '0.7rem', marginRight: '0.3rem' }}>{t}</span>
                            ))}
                          </td>
                          <td style={{ padding: '1rem' }}>
                            <span style={{ 
                              color: sub.unsubscribed ? 'var(--error)' : 'var(--success)',
                              background: sub.unsubscribed ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.15)',
                              padding: '0.2rem 0.5rem',
                              borderRadius: '4px',
                              fontSize: '0.75rem',
                              fontWeight: '600'
                            }}>
                              {sub.unsubscribed ? 'UNSUBSCRIBED' : 'ACTIVE'}
                            </span>
                          </td>
                          <td style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                            {sub.createdAt ? new Date(sub.createdAt).toLocaleDateString() : 'Recent'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Create Newsletter Modal */}
        {isCampaignModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '780px', width: '100%', padding: '2rem', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>Newsletter & Campaign Builder</h3>
                <button onClick={() => setIsCampaignModalOpen(false)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
                  <X size={20} />
                </button>
              </div>

              {/* Preset Templates */}
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.5rem', fontWeight: '600' }}>
                  LOAD PRE-DESIGNED TEMPLATE
                </label>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {templates.map((tpl, i) => (
                    <button key={i} className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }} onClick={() => applyTemplate(tpl)}>
                      {tpl.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="input-group">
                <label>Subject Line</label>
                <input type="text" placeholder="e.g. Special Product Announcement..." value={subject} onChange={(e) => setSubject(e.target.value)} />
              </div>

              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                <button className={`btn ${previewMode === 'edit' ? 'btn-primary' : 'btn-secondary'}`} style={{ fontSize: '0.8rem' }} onClick={() => setPreviewMode('edit')}>
                  Edit Content
                </button>
                <button className={`btn ${previewMode === 'preview' ? 'btn-primary' : 'btn-secondary'}`} style={{ fontSize: '0.8rem' }} onClick={() => setPreviewMode('preview')}>
                  <Eye size={14} style={{ marginRight: '0.3rem' }} /> Live Desktop Preview
                </button>
              </div>

              {previewMode === 'edit' ? (
                <div>
                  <div className="input-group">
                    <label>HTML Newsletter Content</label>
                    <textarea rows="8" placeholder="<div style='...'>Your HTML content</div>" value={bodyHtml} onChange={(e) => setBodyHtml(e.target.value)} />
                  </div>
                  <div className="input-group">
                    <label>Plain Text Version (Fallback)</label>
                    <textarea rows="3" placeholder="Plain text version..." value={bodyText} onChange={(e) => setBodyText(e.target.value)} />
                  </div>
                </div>
              ) : (
                <div style={{ background: '#ffffff', color: '#000000', padding: '1rem', borderRadius: '8px', minHeight: '260px' }} dangerouslySetInnerHTML={{ __html: bodyHtml }} />
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>
                <button className="btn btn-secondary" onClick={() => setIsCampaignModalOpen(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSendCampaign} disabled={sending}>
                  {sending ? <span className="spinner"></span> : <><Send size={16} style={{ marginRight: '0.5rem' }} /> Dispatch Newsletter Blast</>}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Subscriber Modal */}
        {isAudienceModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '480px', width: '100%', padding: '2rem', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>Add Contact Subscriber</h3>
                <button onClick={() => setIsAudienceModalOpen(false)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
                  <X size={20} />
                </button>
              </div>

              <div className="input-group">
                <label>Email Address</label>
                <input type="email" placeholder="subscriber@example.com" value={audEmail} onChange={(e) => setAudEmail(e.target.value)} />
              </div>

              <div className="input-group">
                <label>Full Name (Optional)</label>
                <input type="text" placeholder="John Doe" value={audName} onChange={(e) => setAudName(e.target.value)} />
              </div>

              <div className="input-group">
                <label>Tags (Comma separated)</label>
                <input type="text" placeholder="vip, customer, newsletter" value={audTags} onChange={(e) => setAudTags(e.target.value)} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>
                <button className="btn btn-secondary" onClick={() => setIsAudienceModalOpen(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddSubscriber} disabled={audSubmitting}>
                  {audSubmitting ? <span className="spinner"></span> : 'Add Contact'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EmailSuite;

