import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../config';
import { Mail, Users, Tag, Plus, Send, Eye, Search, X, CheckCircle2, TrendingUp, MousePointer, AlertOctagon, Sparkles, Edit3, AlertTriangle, Settings, Link2 } from 'lucide-react';

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

  // Edit / preview an existing campaign before it goes out.
  const [editing, setEditing] = useState(null);
  const [editSubject, setEditSubject] = useState('');
  const [editBodyHtml, setEditBodyHtml] = useState('');
  const [editBodyText, setEditBodyText] = useState('');
  const [editTab, setEditTab] = useState('preview');   // 'preview' | 'edit'
  const [savingEdit, setSavingEdit] = useState(false);
  const [sendingEdit, setSendingEdit] = useState(false);

  // Sending credentials for this business.
  const [emailCfg, setEmailCfg] = useState(null);
  const [showCfg, setShowCfg] = useState(false);
  const [cfgKey, setCfgKey] = useState('');
  const [cfgFrom, setCfgFrom] = useState('');
  const [cfgName, setCfgName] = useState('');
  const [cfgReply, setCfgReply] = useState('');
  const [savingCfg, setSavingCfg] = useState(false);

  useEffect(() => {
    fetchCampaigns();
    fetchAudiences();
    fetchEmailConfig();
  }, [activeWorkspaceId]);

  const fetchEmailConfig = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/email-config`, {}, token);
      if (!res.ok) return;
      const cfg = await res.json();
      setEmailCfg(cfg);
      setCfgFrom(cfg.fromEmail || '');
      setCfgName(cfg.fromName || '');
      setCfgReply(cfg.replyTo || '');
    } catch {
      /* non-fatal — the page still works without it */
    }
  };

  const saveEmailConfig = async () => {
    if (!cfgFrom.trim()) return showToast('Enter the address campaigns should send from', true);
    setSavingCfg(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/email-config`, {
        method: 'POST',
        body: JSON.stringify({
          provider: 'resend',
          apiKey: cfgKey || null,
          fromEmail: cfgFrom,
          fromName: cfgName || null,
          replyTo: cfgReply || null,
        }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Could not save email settings');
      showToast(data.message || 'Email connected.');
      setCfgKey('');
      setShowCfg(false);
      await fetchEmailConfig();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSavingCfg(false);
    }
  };

  const openEditor = (camp) => {
    setEditing(camp);
    setEditSubject(camp.subject || '');
    setEditBodyHtml(camp.bodyHtml || '');
    setEditBodyText(camp.bodyText || '');
    setEditTab('preview');
  };

  const saveDraft = async ({ send } = { send: false }) => {
    if (!editing) return;
    if (!editSubject.trim()) return showToast('A subject line is required', true);
    if (send && !window.confirm(
      `Send "${editSubject}" to every subscriber of this business? This cannot be undone.`
    )) return;

    send ? setSendingEdit(true) : setSavingEdit(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/emails/${editing.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          subject: editSubject,
          bodyHtml: editBodyHtml,
          bodyText: editBodyText,
          ...(send ? { status: 'SENT' } : {}),
        }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);

      // The server decides whether a send actually succeeded — trust its
      // status, not the fact that the request returned 200.
      if (send) {
        if (data.status === 'SENT') {
          showToast('Campaign sent.');
          setEditing(null);
        } else {
          showToast(data.errorLog || 'The send failed. See the campaign for details.', true);
        }
      } else {
        showToast('Draft saved.');
        setEditing(null);
      }
      await fetchCampaigns();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSavingEdit(false);
      setSendingEdit(false);
    }
  };

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

  const inputStyle = {
    width: '100%', padding: '0.55rem 0.75rem', borderRadius: 8,
    background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)',
    color: 'var(--text-main)', fontSize: '0.86rem',
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
  // Never invent performance figures. These previously fell back to "24.5" and
  // "4.2" when nothing had been sent, which reads as real data and would be a
  // lie in front of a customer.
  const avgOpenRate = totalSent > 0 ? ((totalOpens / totalSent) * 100).toFixed(1) : null;
  const avgCtr = totalOpens > 0 ? ((totalClicks / totalOpens) * 100).toFixed(1) : null;

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

        {/* SENDING STATUS — a campaign cannot go anywhere without this. */}
        {activeTab === 'campaigns' && emailCfg && (
          <div className="glass-panel" style={{
            padding: '1.15rem 1.5rem', marginBottom: '1.5rem',
            border: emailCfg.configured ? '1px solid var(--border-color)' : '1px solid rgba(245,158,11,0.35)',
            background: emailCfg.configured ? undefined : 'rgba(245,158,11,0.06)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', flexWrap: 'wrap' }}>
              {emailCfg.configured
                ? <CheckCircle2 size={17} color="var(--success)" />
                : <AlertTriangle size={17} color="#f59e0b" />}
              <div style={{ flex: 1, minWidth: 240 }}>
                <div style={{ fontSize: '0.92rem', fontWeight: 600 }}>
                  {emailCfg.configured
                    ? (emailCfg.usingPlatformDefault
                        ? 'Sending through the platform’s shared address'
                        : `Sending as ${emailCfg.fromEmail}`)
                    : 'Email sending is not connected'}
                </div>
                <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  {emailCfg.configured
                    ? (emailCfg.usingPlatformDefault
                        ? 'Connect your own domain so mail comes from your brand and lands in inboxes rather than spam.'
                        : 'Campaigns send from your own domain.')
                    : 'Campaigns cannot be delivered until you add a sending key. Drafts are still saved.'}
                </p>
              </div>
              <button className="btn btn-secondary" onClick={() => setShowCfg(v => !v)}
                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.45rem 0.9rem', fontSize: '0.83rem' }}>
                <Link2 size={14} /> {showCfg ? 'Hide' : emailCfg.configured && !emailCfg.usingPlatformDefault ? 'Change' : 'Connect email'}
              </button>
            </div>

            {emailCfg.lastError && (
              <p style={{ margin: '0.7rem 0 0 0', fontSize: '0.8rem', color: '#fca5a5' }}>
                Last send error: {emailCfg.lastError}
              </p>
            )}

            {showCfg && (
              <div style={{ marginTop: '1.2rem', paddingTop: '1.2rem', borderTop: '1px solid var(--border-color)', display: 'grid', gap: '0.85rem' }}>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
                  Paste a <strong>Resend</strong> API key and the address you have verified with them.
                  Mail then leaves from your domain, which is what keeps it out of spam folders.
                  The key is encrypted before it is stored and never shown again.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.85rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                      API key {emailCfg.hasKey && <span style={{ color: 'var(--success)' }}>· saved</span>}
                    </label>
                    <input type="password" value={cfgKey} onChange={e => setCfgKey(e.target.value)}
                      placeholder={emailCfg.hasKey ? '••••••••  (leave blank to keep)' : 're_...'}
                      style={inputStyle} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Send from</label>
                    <input type="email" value={cfgFrom} onChange={e => setCfgFrom(e.target.value)}
                      placeholder="hello@yourdomain.com" style={inputStyle} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Sender name</label>
                    <input type="text" value={cfgName} onChange={e => setCfgName(e.target.value)}
                      placeholder="Your Brand" style={inputStyle} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Reply-to (optional)</label>
                    <input type="email" value={cfgReply} onChange={e => setCfgReply(e.target.value)}
                      placeholder="support@yourdomain.com" style={inputStyle} />
                  </div>
                </div>
                <button className="btn btn-primary" onClick={saveEmailConfig} disabled={savingCfg}
                  style={{ width: 'fit-content', padding: '0.5rem 1.1rem', fontSize: '0.85rem' }}>
                  {savingCfg ? 'Saving…' : 'Save sending settings'}
                </button>
              </div>
            )}
          </div>
        )}

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
                <div style={{ textAlign: 'center', padding: '4rem 0', color: 'var(--text-muted)', background: 'rgba(11, 16, 32, 0.03)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                  No email campaigns created yet for this workspace.
                </div>
              ) : (
                campaigns.map(camp => (
                  <div key={camp.id} style={{ background: 'rgba(0,0,0,0.3)', padding: '1.25rem', borderRadius: '14px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 260 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                        <span style={{
                          fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 700,
                          padding: '0.18rem 0.55rem', borderRadius: 4,
                          background: camp.status === 'SENT' ? 'rgba(16,185,129,0.15)'
                            : camp.status === 'FAILED' ? 'rgba(239,68,68,0.15)'
                            : 'rgba(245,158,11,0.15)',
                          color: camp.status === 'SENT' ? 'var(--success)'
                            : camp.status === 'FAILED' ? '#f87171'
                            : '#f59e0b',
                        }}>
                          {camp.status}
                        </span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: '600' }}>
                          {camp.type}
                        </span>
                      </div>
                      <p style={{ margin: '0 0 0.4rem 0', fontSize: '1.05rem', fontWeight: '600' }}>{camp.subject}</p>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {camp.status === 'SENT' && camp.sentAt
                          ? `Sent ${new Date(camp.sentAt).toLocaleString()} • ${camp.recipientCount || 0} recipients`
                          : camp.createdAt ? `Created ${new Date(camp.createdAt).toLocaleString()}` : ''}
                      </p>

                      {/* Recorded all along, never shown. */}
                      {camp.status === 'FAILED' && camp.errorLog && (
                        <div style={{ marginTop: '0.6rem', padding: '0.5rem 0.7rem', borderRadius: 7, background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)', maxWidth: 480 }}>
                          <p style={{ margin: 0, fontSize: '0.75rem', color: '#fca5a5', lineHeight: 1.5 }}>
                            {camp.errorLog}
                          </p>
                        </div>
                      )}
                    </div>

                    <button className="btn btn-secondary" onClick={() => openEditor(camp)}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.95rem', fontSize: '0.85rem' }}>
                      {camp.status === 'SENT' ? <><Eye size={15} /> View</> : <><Edit3 size={15} /> Edit / Preview</>}
                    </button>
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
                  <h2 style={{ margin: 0, fontSize: '1.75rem', color: avgOpenRate ? 'var(--success)' : 'var(--text-muted)' }}>
                    {avgOpenRate ? `${avgOpenRate}%` : '—'}
                  </h2>
                </div>
              </div>

              <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(59, 130, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <MousePointer size={24} color="var(--secondary-color)" />
                </div>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '600' }}>CLICK-THROUGH RATE</span>
                  <h2 style={{ margin: 0, fontSize: '1.75rem', color: avgCtr ? 'var(--secondary-color)' : 'var(--text-muted)' }}>
                    {avgCtr ? `${avgCtr}%` : '—'}
                  </h2>
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
                        <tr key={sub.id} style={{ borderBottom: '1px solid rgba(11, 16, 32, 0.05)' }}>
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
        {/* EDIT / PREVIEW an existing campaign */}
        {editing && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ width: '100%', maxWidth: 980, maxHeight: '90vh', borderRadius: 16, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

              <div style={{ padding: '1.1rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Mail size={18} color="var(--primary-color)" />
                <h3 style={{ margin: 0, fontSize: '1.05rem' }}>
                  {editing.status === 'SENT' ? 'Sent campaign' : 'Edit / Preview'}
                </h3>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem' }}>
                  {['preview', 'edit'].map(t => (
                    <button key={t} onClick={() => setEditTab(t)}
                      className={`btn ${editTab === t ? 'btn-primary' : 'btn-secondary'}`}
                      style={{ padding: '0.35rem 0.85rem', fontSize: '0.8rem', textTransform: 'capitalize' }}>
                      {t}
                    </button>
                  ))}
                  <button onClick={() => setEditing(null)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.35rem', display: 'flex' }}>
                    <X size={18} />
                  </button>
                </div>
              </div>

              <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>
                {editTab === 'edit' ? (
                  <div style={{ display: 'grid', gap: '1rem' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                        Subject line <span style={{ color: editSubject.length > 55 ? '#f59e0b' : 'var(--text-muted)' }}>({editSubject.length}/55 recommended)</span>
                      </label>
                      <input value={editSubject} onChange={e => setEditSubject(e.target.value)} style={inputStyle} />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>HTML body</label>
                      <textarea rows={14} value={editBodyHtml} onChange={e => setEditBodyHtml(e.target.value)}
                        style={{ ...inputStyle, fontFamily: 'monospace', fontSize: '0.78rem', lineHeight: 1.6, resize: 'vertical' }} />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                        Plain-text version — shown by clients that block HTML
                      </label>
                      <textarea rows={5} value={editBodyText} onChange={e => setEditBodyText(e.target.value)}
                        style={{ ...inputStyle, resize: 'vertical' }} />
                    </div>
                  </div>
                ) : (
                  <div>
                    {/* Inbox chrome, so the subject is judged the way a
                        recipient actually sees it. */}
                    <div style={{ maxWidth: 640, margin: '0 auto' }}>
                      <div style={{ background: 'rgba(11, 16, 32, 0.04)', border: '1px solid var(--border-color)', borderRadius: '10px 10px 0 0', padding: '0.9rem 1.1rem' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          From: {emailCfg?.fromName || emailCfg?.fromEmail || 'your business'}
                          {emailCfg?.fromEmail && emailCfg?.fromName ? ` <${emailCfg.fromEmail}>` : ''}
                        </div>
                        <div style={{ fontSize: '1rem', fontWeight: 700, marginTop: '0.3rem' }}>
                          {editSubject || <span style={{ color: 'var(--text-muted)' }}>(no subject)</span>}
                        </div>
                      </div>
                      <div style={{ background: '#ffffff', borderRadius: '0 0 10px 10px', minHeight: 260, overflow: 'hidden' }}>
                        {editBodyHtml ? (
                          <iframe
                            title="Email preview"
                            srcDoc={editBodyHtml}
                            sandbox=""
                            style={{ width: '100%', height: 420, border: 'none', background: '#fff' }}
                          />
                        ) : (
                          <div style={{ padding: '2rem', color: '#666', fontFamily: 'Arial, sans-serif', whiteSpace: 'pre-wrap' }}>
                            {editBodyText || 'This campaign has no content yet. Switch to Edit to write it.'}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div style={{ padding: '1.1rem 1.5rem', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: 'auto' }}>
                  {editing.status === 'SENT'
                    ? `Delivered to ${editing.recipientCount || 0} subscribers`
                    : `Will send to ${audiences.length} subscriber${audiences.length === 1 ? '' : 's'}`}
                </span>

                {editing.status !== 'SENT' && (
                  <>
                    <button className="btn btn-secondary" onClick={() => saveDraft({ send: false })} disabled={savingEdit || sendingEdit}
                      style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
                      {savingEdit ? 'Saving…' : 'Save draft'}
                    </button>
                    <button className="btn btn-primary" onClick={() => saveDraft({ send: true })}
                      disabled={savingEdit || sendingEdit || audiences.length === 0 || !emailCfg?.configured}
                      title={
                        audiences.length === 0 ? 'No subscribers to send to'
                          : !emailCfg?.configured ? 'Connect email sending first'
                          : ''
                      }
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1.1rem', fontSize: '0.85rem' }}>
                      {sendingEdit ? <><span className="spinner" style={{ width: 13, height: 13 }} /> Sending…</> : <><Send size={15} /> Send now</>}
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {isCampaignModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '780px', width: '100%', padding: '2rem', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>Newsletter & Campaign Builder</h3>
                <button onClick={() => setIsCampaignModalOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer' }}>
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
                <button onClick={() => setIsAudienceModalOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-main)', cursor: 'pointer' }}>
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

