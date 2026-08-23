import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch, apiError} from '../config';
import { useWorkspace } from './WorkspaceContext';
import { 
  Send, 
  Sparkles, 
  Copy, 
  Check, 
  RefreshCw, 
  Share2, 
  MessageSquare, 
  Heart, 
  Repeat, 
  BarChart2, 
  ArrowUp, 
  Calendar,
  Building2,
  CheckCircle2,
  Layers,
  Flame,
  Globe
} from 'lucide-react';

export default function PostShipStudio({ token, showToast, activeWorkspaceId }) {
  const { activeWorkspace, workspaces } = useWorkspace();
  
  // Resolve current active business details dynamically
  const currentWorkspace = activeWorkspace || workspaces?.find(w => w.id === activeWorkspaceId) || workspaces?.[0] || null;
  const businessName = currentWorkspace?.name || 'Organiflo';
  const cleanHandle = `@${(businessName || 'organiflo').toLowerCase().replace(/[^a-z0-9]/g, '')}`;
  const industry = currentWorkspace?.industry || currentWorkspace?.businessModel || 'AI SaaS';

  const [inputText, setInputText] = useState('');
  const [generating, setGenerating] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [copiedKey, setCopiedKey] = useState(null);

  // The preview shown before anything is generated.
  //
  // It used to be one builder's story with the business name substituted in,
  // which reads as nonsense for anyone who is not a software founder: a
  // skincare shop was shown "a render race that only appeared with 2+ tabs
  // open" and asked how other builders at their store debug it. The sample
  // now follows the business model, the same way the closing CTA does.
  const sampleFor = (model) => {
    const m = (model || '').toLowerCase();
    if (m.includes('commerce') || m.includes('retail') || m.includes('shop')) {
      return {
        x: `restocked the one thing people kept emailing about.

sold out in nine days last time. we made twice as many.

that is the whole update.`,
        hook: 'We sold out in nine days and it taught us more than the launch did.',
        li: `We sold out in nine days and it taught us more than the launch did.

Every email after that asked the same question, so we stopped guessing and made twice as many.

Listening beats forecasting, every time.`,
        sub: 'r/smallbusiness',
        title: 'Sold out in nine days. The emails afterwards were the real product research.',
        body: `We launched expecting a slow month and ran out in nine days.

The useful part was not the sales, it was that every email afterwards asked the same question. That told us what to make next.

How do you decide restock quantities?`,
      };
    }
    if (m.includes('page') || m.includes('creator') || m.includes('influencer')) {
      return {
        x: `posted every day for thirty days.

the one that worked was the one i almost deleted.

post it anyway.`,
        hook: 'I posted every day for thirty days. The best one was the one I almost deleted.',
        li: `I posted every day for thirty days.

The post that reached the most people was the one I nearly deleted for being too simple.

Taste is a bad predictor of reach. Volume is a good one.`,
        sub: 'r/NewTubers',
        title: 'Thirty days of posting: the winner was the one I almost deleted',
        body: `I committed to thirty days. The post that outperformed everything was the simplest one, which I nearly cut for being obvious.

Has anyone else found their instincts are backwards on this?`,
      };
    }
    return {
      x: `shipped the boring feature today.

three weeks on the clever one: four people used it. this took an afternoon and it is the one people thank us for.

build the boring thing.`,
      hook: 'Three weeks on the clever feature. Four people used it.',
      li: `Three weeks on the clever feature. Four people used it.

Then we shipped the boring one in an afternoon, and it is the change people actually write in to thank us for.

Build the boring thing that works.`,
      sub: 'r/SideProject',
      title: 'Three weeks on the clever feature. Four people used it.',
      body: `We spent three weeks on the feature we were proud of and four people touched it.

The afternoon feature is the one support hears about. I keep relearning this.

How do you decide what is worth building?`,
    };
  };

  const sample = sampleFor(currentWorkspace?.businessModel || industry);

  const [bundle, setBundle] = useState(null);

  // Re-label the previews when the active business changes.
  //
  // `prev` is null until something has been generated — the composer starts
  // empty on purpose. Spreading `...prev.x_post` in that state threw
  // "Cannot read properties of null" during render and white-screened the
  // whole page. There is nothing to re-label before there is a bundle.
  useEffect(() => {
    if (!businessName) return;
    setBundle(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        x_post: {
          ...prev.x_post,
          handle: cleanHandle,
          display_name: businessName,
        },
        linkedin_post: {
          ...prev.linkedin_post,
          author_name: businessName,
          headline: `Founder at ${businessName}`,
        },
      };
    });
  }, [businessName, cleanHandle]);

  const handleGenerate = async (e) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) {
      showToast?.('Enter an idea, changelog line, or product URL', true);
      return;
    }

    setGenerating(true);
    try {
      const res = await authFetch(
        `${API_BASE}/creatives/postship-generate`,
        {
          method: 'POST',
          headers: activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {},
          body: JSON.stringify({
            input_text: inputText,
            url: inputText.startsWith('http') ? inputText : null,
          }),
        },
        token
      );

      const data = await res.json();
      if (res.ok && data.bundle) {
        setBundle(data.bundle);
        showToast?.(`Generated 3 native posts for ${businessName}! 🚀`);
      } else {
        showToast?.(apiError(data, 'Generation failed'), true);
      }
    } catch (err) {
      showToast?.('Error generating multi-platform posts', true);
    } finally {
      setGenerating(false);
    }
  };

  const handleScheduleToQueue = async () => {
    if (!inputText.trim()) {
      showToast?.('Please generate posts before scheduling', true);
      return;
    }

    setScheduling(true);
    try {
      const res = await authFetch(
        `${API_BASE}/creatives/postship-generate`,
        {
          method: 'POST',
          headers: activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {},
          body: JSON.stringify({
            input_text: inputText,
            url: inputText.startsWith('http') ? inputText : null,
            schedule_to_queue: true,
          }),
        },
        token
      );

      const data = await res.json();
      if (res.ok) {
        // Say what was queued and where. The old message claimed success
        // whatever came back -- including the case where no account was
        // connected and nothing at all had been scheduled.
        const queued = data.queued || [];
        if (queued.length === 0) {
          showToast?.(
            'Nothing was queued — connect X, LinkedIn or Facebook first, then try again.',
            true,
          );
        } else {
          const names = queued
            .map((q) => (q.platform === 'TWITTER' ? 'X' : q.platform[0] + q.platform.slice(1).toLowerCase()))
            .join(', ');
          showToast?.(`Queued to ${names}. First one goes out shortly, the rest are spaced out.`);
        }
      } else {
        showToast?.(apiError(data, 'Could not schedule to queue'), true);
      }
    } catch (err) {
      showToast?.('Error scheduling to queue', true);
    } finally {
      setScheduling(false);
    }
  };

  const copyText = (text, key, label) => {
    navigator.clipboard?.writeText(text);
    setCopiedKey(key);
    showToast?.(`${label} copied to clipboard!`);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  const initials = (businessName || 'OR')
    .split(' ')
    .map(n => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || 'OR';

  // These used to be four hardcoded engineering anecdotes, offered to a
  // florist and a clinic alike. sampleFor already shapes the output to the
  // business; the prompts that start the process should match it, or the tool
  // opens by suggesting somebody else's story.
  const quickIdeasFor = (model) => {
    const m = (model || '').toLowerCase();

    if (m.includes('commerce') || m.includes('retail') || m.includes('shop')) {
      return [
        `The product ${businessName} sells most, and what people ask before buying it`,
        `What we changed after reading a month of customer emails`,
        `A restock that sold out, and what we got wrong about the quantity`,
        `The question we get asked most, answered properly`,
      ];
    }

    if (m.includes('page') || m.includes('creator') || m.includes('influencer')) {
      return [
        `The post that worked that I almost did not publish`,
        `What thirty days of posting actually taught me`,
        `The thing everyone asks me in the comments`,
        `What I would tell myself before I started ${businessName}`,
      ];
    }

    if (m.includes('local') || m.includes('service') || m.includes('clinic')) {
      return [
        `The mistake customers make before they call ${businessName}`,
        `What actually happens on a first visit`,
        `The question we answer every single week`,
        `Why the cheapest option usually costs more`,
      ];
    }

    return [
      `What we shipped this week at ${businessName}, and why`,
      `The step where people get stuck, and what we changed`,
      `A mistake we made scaling, written up honestly`,
      `The question customers ask before they sign up`,
    ];
  };

  const quickIdeas = quickIdeasFor(currentWorkspace?.businessModel || industry);

  // What the composer starts from when somebody would rather not think of a
  // line themselves. Built from the workspace's own description and audience,
  // so it is a sentence about this business rather than a prompt template.
  const [fillIndex, setFillIndex] = useState(0);

  const autofillLines = () => {
    const audience = (currentWorkspace?.targetAudience || '').trim();
    const summary = (currentWorkspace?.description || '').trim();
    const lines = [];

    if (summary) {
      // Their own first sentence is the most accurate thing available.
      const firstSentence = summary.split(/(?<=[.!?])\s/)[0].trim();
      if (firstSentence.length > 12) lines.push(firstSentence);
    }
    if (audience) {
      lines.push(`The thing ${audience} get wrong before they find ${businessName}`);
    }
    lines.push(...quickIdeas);
    return lines;
  };

  const autofill = () => {
    const lines = autofillLines();
    if (!lines.length) return;
    setInputText(lines[fillIndex % lines.length]);
    setFillIndex((i) => i + 1);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Platform Banner Card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(139, 92, 246, 0.04) 100%)',
        borderRadius: 14,
        padding: '1.75rem 2rem',
        border: '1px solid rgba(37, 99, 235, 0.25)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1.25rem',
      }}>
        <div style={{ maxWidth: 640 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.2rem 0.65rem',
              borderRadius: 16,
              background: 'rgba(37,99,235,0.12)',
              border: '1px solid rgba(37,99,235,0.3)',
              fontSize: '0.72rem',
              fontWeight: 800,
              color: 'var(--primary-color)',
              textTransform: 'uppercase',
              letterSpacing: '.06em',
            }}>
              <Send size={12} /> Publishing Engine
            </span>

            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.2rem 0.65rem',
              borderRadius: 16,
              background: 'rgba(16,185,129,0.12)',
              border: '1px solid rgba(16,185,129,0.3)',
              fontSize: '0.72rem',
              fontWeight: 800,
              color: 'var(--success)',
            }}>
              <Building2 size={12} /> Active: {businessName} ({industry})
            </span>
          </div>

          <h2 style={{ fontSize: '1.65rem', fontWeight: 800, margin: '0 0 0.35rem', color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
            One Click. Every Platform, Natively.
          </h2>
          <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            The same ship line, rewritten for how each platform actually reads — not copy-pasted three times. Tailored specifically for <strong style={{ color: 'var(--text-main)' }}>{businessName}</strong>.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={handleScheduleToQueue}
            disabled={scheduling || generating}
            className="btn"
            style={{
              background: 'rgba(16,185,129,0.15)',
              color: 'var(--success)',
              border: '1px solid rgba(16,185,129,0.35)',
              padding: '0.65rem 1.15rem',
              fontSize: '0.84rem',
              fontWeight: 700,
              borderRadius: 10,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
            }}
          >
            {scheduling ? <RefreshCw className="spin" size={14} /> : <Calendar size={14} />}
            {scheduling ? 'Scheduling...' : 'Schedule All to Queue'}
          </button>
        </div>
      </div>

      {/* Input Form Box */}
      <div style={{ padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 14, border: '1px solid var(--border-color)' }}>
        <form onSubmit={handleGenerate}>
          <label style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Sparkles size={14} color="var(--primary-color)" /> Idea, Ship Line, Changelog, or URL for {businessName}:
          </label>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{
              flex: 1,
              minWidth: 260,
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(11, 16, 32, 0.04)',
              border: '1px solid var(--border-color)',
              borderRadius: 10,
              padding: '0.45rem 0.85rem',
            }}>
              <span style={{ color: 'var(--primary-color)', fontWeight: 800, marginRight: '0.5rem' }}>&gt;</span>
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={`e.g. Shipped new automated scheduling for ${businessName}, or paste URL...`}
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: 'var(--text-main)',
                  fontSize: '0.88rem',
                }}
              />
            </div>

            <button
              type="button"
              onClick={autofill}
              title="Fill this from your business details"
              style={{
                marginTop: '0.6rem',
                marginRight: '0.6rem',
                background: 'transparent',
                border: '1px solid var(--border-color)',
                borderRadius: 10,
                padding: '0.5rem 0.85rem',
                minHeight: 40,
                fontSize: '0.8rem',
                fontWeight: 700,
                color: 'var(--primary-color)',
                cursor: 'pointer',
              }}
            >
              ✨ Autofill from {businessName}
            </button>

            <button
              type="submit"
              disabled={generating}
              className="btn btn-primary"
              style={{
                padding: '0.65rem 1.4rem',
                fontWeight: 800,
                fontSize: '0.86rem',
                borderRadius: 10,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
                boxShadow: '0 4px 14px rgba(37,99,235,0.25)',
              }}
            >
              {generating ? <RefreshCw className="spin" size={15} /> : <Sparkles size={15} />}
              {generating ? 'Rewriting...' : 'Generate 3 Native Posts'}
            </button>
          </div>
        </form>

        {/* Quick Idea Pills */}
        <div style={{ marginTop: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>Quick Ideas:</span>
          {quickIdeas.map((idea, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => { setInputText(idea); }}
              style={{
                background: 'rgba(11, 16, 32, 0.03)',
                border: '1px solid var(--border-color)',
                borderRadius: 14,
                padding: '0.2rem 0.6rem',
                fontSize: '0.72rem',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--primary-color)'; e.currentTarget.style.borderColor = 'var(--primary-color)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.borderColor = 'var(--border-color)'; }}
            >
              {idea.slice(0, 36)}...
            </button>
          ))}
        </div>
      </div>

      {/* 3 Native Platform Cards (X, LinkedIn, Reddit) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: '1.25rem',
        alignItems: 'stretch',
      }}>
        
        {/* ========================================================================= */}
        {/* CARD 1: X (TWITTER) NATIVE CARD */}
        {/* ========================================================================= */}
        <div style={{
          background: 'rgba(11,16,32,0.03)',
          borderRadius: 14,
          border: '1px solid var(--border-color)',
          padding: '1.35rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
          boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
        }}>
          <div>
            {/* Header Badge */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.65rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                𝕏 Native Build-In-Public Post
              </span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                Max 280 Chars
              </span>
            </div>

            {/* Author Row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.85rem' }}>
              <div style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--secondary-color), var(--secondary-color))',
                color: 'var(--text-main)',
                fontWeight: 800,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ lineHeight: 1.25, overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <span style={{ fontWeight: 800, color: 'var(--text-main)', fontSize: '0.88rem', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                    {bundle?.x_post?.display_name || businessName}
                  </span>
                  <span style={{ color: '#38bdf8', fontSize: '0.75rem' }}>●</span>
                </div>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>{bundle?.x_post?.handle || cleanHandle} · 2h</span>
              </div>
            </div>

            {/* Post Content */}
            <p style={{
              fontSize: '0.86rem',
              color: 'var(--text-main)',
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
              margin: '0 0 1.25rem',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
            }}>
              {bundle?.x_post?.content || (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Your X post appears here — short, lowercase, one idea.
                </span>
              )}
            </p>
          </div>

          <div>
            {/* Metric Footer */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '0.75rem',
              borderTop: '1px solid var(--border-color)',
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
              marginBottom: '0.85rem',
            }}>
              {(() => {
                const used = (bundle?.x_post?.content || '').length;
                const over = used > 280;
                return (
                  <>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: over ? 'var(--error)' : 'var(--text-muted)', fontWeight: over ? 700 : 500 }}>
                      <MessageSquare size={13} /> {used} / 280 characters
                    </span>
                    <span>{over ? 'Too long — X will refuse it' : 'Posts as one tweet'}</span>
                  </>
                );
              })()}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 700 }}>
                ● Thread Ready
              </span>
              <button
                onClick={() => copyText(bundle?.x_post?.content || '', 'x', 'X Post')}
                className="btn"
                style={{
                  background: copiedKey === 'x' ? 'rgba(16,185,129,0.2)' : 'rgba(255,255,255,0.08)',
                  color: copiedKey === 'x' ? '#10b981' : '#fff',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  padding: '0.35rem 0.75rem',
                  borderRadius: 8,
                  border: '1px solid var(--border-color)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                {copiedKey === 'x' ? <Check size={12} /> : <Copy size={12} />}
                {copiedKey === 'x' ? 'Copied!' : 'Copy for X'}
              </button>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* CARD 2: LINKEDIN NATIVE CARD */}
        {/* ========================================================================= */}
        <div style={{
          background: '#ffffff',
          borderRadius: 14,
          border: '1px solid #e2e8f0',
          padding: '1.35rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
          color: '#18181b',
          boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
        }}>
          <div>
            {/* Header Badge */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid #f1f5f9', paddingBottom: '0.65rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#0a66c2', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                💼 LinkedIn Story Post
              </span>
              <span style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: 700 }}>
                High-Retention Hook
              </span>
            </div>

            {/* Author Row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.85rem' }}>
              <div style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                background: '#0a66c2',
                color: 'var(--text-main)',
                fontWeight: 800,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                {initials}
              </div>
              <div style={{ lineHeight: 1.25, overflow: 'hidden' }}>
                <div style={{ fontWeight: 800, color: '#0f172a', fontSize: '0.88rem', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                  {bundle?.linkedin_post?.author_name || businessName} <span style={{ color: '#64748b', fontSize: '0.74rem' }}>· 1st</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                  {bundle?.linkedin_post?.headline || `Founder at ${businessName}`}
                </div>
                <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>now · 🌐</span>
              </div>
            </div>

            {/* Post Content */}
            <p style={{
              fontSize: '0.84rem',
              color: '#1e293b',
              lineHeight: 1.55,
              whiteSpace: 'pre-wrap',
              margin: '0 0 1.25rem',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
            }}>
              {bundle?.linkedin_post?.content || (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  Your LinkedIn post appears here — a hook line, then the story.
                </span>
              )}
            </p>
          </div>

          <div>
            {/* Metric Footer */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '0.75rem',
              borderTop: '1px solid #f1f5f9',
              fontSize: '0.74rem',
              color: '#64748b',
              marginBottom: '0.85rem',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                {(() => {
                  const body = bundle?.linkedin_post?.content || '';
                  const shown = body.slice(0, 140);
                  return body.length > 140
                    ? `First ${shown.length} characters show before “see more”`
                    : 'Shows in full, no “see more”';
                })()}
              </span>
              <span>{(bundle?.linkedin_post?.content || '').length} characters</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', color: '#0a66c2', fontWeight: 800 }}>
                📈 Founder Insight
              </span>
              <button
                onClick={() => copyText(bundle?.linkedin_post?.content || '', 'li', 'LinkedIn Post')}
                className="btn"
                style={{
                  background: copiedKey === 'li' ? '#10b981' : '#0a66c2',
                  color: 'var(--text-main)',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  padding: '0.35rem 0.75rem',
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                {copiedKey === 'li' ? <Check size={12} /> : <Copy size={12} />}
                {copiedKey === 'li' ? 'Copied!' : 'Copy for LinkedIn'}
              </button>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* CARD 3: REDDIT NATIVE CARD */}
        {/* ========================================================================= */}
        <div style={{
          background: 'var(--bg-card)',
          borderRadius: 14,
          border: '1px solid var(--border-color)',
          padding: '1.35rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
          boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
        }}>
          <div>
            {/* Header Badge */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.65rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--primary-color)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                🤖 Reddit Community Post
              </span>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                Zero Fluff
              </span>
            </div>

            {/* Subreddit Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <div style={{
                width: 26,
                height: 26,
                borderRadius: '50%',
                background: '#ff4500',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                color: 'var(--text-main)',
                fontWeight: 800,
                flexShrink: 0,
              }}>
                r/
              </div>
              <span style={{ fontWeight: 800, color: 'var(--text-main)', fontSize: '0.84rem' }}>
                {bundle?.reddit_post?.subreddit || 'r/SideProject'}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>· 5h</span>
            </div>

            {/* Reddit Title */}
            <h4 style={{
              margin: '0 0 0.65rem',
              fontSize: '0.92rem',
              fontWeight: 800,
              color: 'var(--text-main)',
              lineHeight: 1.35,
            }}>
              {bundle?.reddit_post?.title || (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontWeight: 400 }}>
                  Your Reddit title appears here
                </span>
              )}
            </h4>

            {/* Reddit Body */}
            <p style={{
              fontSize: '0.82rem',
              color: 'var(--text-main)',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              margin: '0 0 1.25rem',
            }}>
              {bundle?.reddit_post?.body || (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  …and the body, written to read like a person rather than a pitch.
                </span>
              )}
            </p>
          </div>

          <div>
            {/* Metric Footer */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.85rem',
              paddingTop: '0.75rem',
              borderTop: '1px solid var(--border-color)',
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
              marginBottom: '0.85rem',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', background: 'rgba(255,69,0,0.10)', padding: '0.2rem 0.5rem', borderRadius: 10 }}>
                <ArrowUp size={13} color="#ff4500" /> {bundle?.reddit_post?.subreddit || 'r/SaaS'}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <MessageSquare size={13} /> Title {(bundle?.reddit_post?.title || '').length} / 300
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <Share2 size={13} /> You post this one yourself
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', color: '#ff4500', fontWeight: 800 }}>
                🤖 Honest Builder Post
              </span>
              <button
                onClick={() => {
                  const block = `${bundle?.reddit_post?.title}\n\n${bundle?.reddit_post?.body}`;
                  copyText(block, 'reddit', 'Reddit Post');
                }}
                className="btn"
                style={{
                  background: copiedKey === 'reddit' ? '#10b981' : '#ff4500',
                  color: 'var(--text-main)',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  padding: '0.35rem 0.75rem',
                  borderRadius: 8,
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                {copiedKey === 'reddit' ? <Check size={12} /> : <Copy size={12} />}
                {copiedKey === 'reddit' ? 'Copied!' : 'Copy for Reddit'}
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
