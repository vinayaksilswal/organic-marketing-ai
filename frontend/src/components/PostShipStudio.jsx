import React, { useState } from 'react';
import { API_BASE, authFetch } from '../config';
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
  ThumbsUp, 
  ArrowUp, 
  ExternalLink,
  Calendar,
  CheckCircle2
} from 'lucide-react';

export default function PostShipStudio({ token, showToast, activeWorkspaceId, businessName = 'Founder' }) {
  const [inputText, setInputText] = useState('Fixed the render race, shipped writing styles');
  const [generating, setGenerating] = useState(false);
  const [bundle, setBundle] = useState({
    x_post: {
      handle: `@${businessName.toLowerCase().replace(/[^a-z0-9]/g, '') || 'martabuilds'}`,
      display_name: businessName || 'Marta Kowalski',
      content: "shipped writing styles today.\n\nthe bug that almost stopped me: a render race that only appeared with 2+ tabs open. 3 hours, 1 line fix.\n\nit's always one line.",
      metrics_estimate: { likes: '310', retweets: '48', replies: '12', views: '21K' }
    },
    linkedin_post: {
      author_name: businessName || 'Marta Kowalski',
      headline: `Founder at ${businessName || 'BuildLog'}`,
      hook_line: 'Three weeks on workspace auth. Four people used it.',
      content: "Three weeks on workspace auth. Four people used it.\n\nThen I shipped autosave in an afternoon — 40 lines — and it's the change people actually thank me for.\n\nBuild the boring thing that works.",
      metrics_estimate: { reactions: '47', comments: '6' }
    },
    reddit_post: {
      subreddit: 'r/SideProject',
      title: 'Spent 3 hours on a bug that was one line. Every time.',
      body: "Render race that only showed up with 2+ tabs open. Logs looked fine. The fix was one line — it's always one line.\n\nCurious how others track these down...",
      metrics_estimate: { upvotes: '248', comments: '32' }
    }
  });

  const handleGenerate = async (e) => {
    if (e) e.preventDefault();
    if (!inputText.trim()) {
      showToast('Enter an idea, changelog line, or product URL', false);
      return;
    }

    setGenerating(true);
    try {
      const res = await authFetch(
        `${API_BASE}/creatives/postship-generate`,
        {
          method: 'POST',
          headers: { 'X-Workspace-Id': activeWorkspaceId },
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
        showToast('Generated 3 native platform posts! 🚀');
      } else {
        showToast(data.detail || 'Generation failed', false);
      }
    } catch (err) {
      showToast('Error generating multi-platform posts', false);
    } finally {
      setGenerating(false);
    }
  };

  const copyText = (text, label) => {
    navigator.clipboard?.writeText(text);
    showToast(`${label} copied to clipboard!`);
  };

  const initials = (businessName || 'MK')
    .split(' ')
    .map(n => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || 'MK';

  return (
    <div style={{
      background: '#0a0d14',
      borderRadius: 20,
      padding: '2.5rem 1.75rem',
      border: '1px solid rgba(255,255,255,0.08)',
      marginBottom: '2.5rem',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background glow effects */}
      <div style={{
        position: 'absolute',
        top: '-10%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '60%',
        height: 180,
        background: 'radial-gradient(ellipse at center, rgba(59, 130, 246, 0.15), transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Header */}
      <div style={{ textAlign: 'center', maxWidth: 640, margin: '0 auto 2rem', position: 'relative' }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.25rem 0.75rem',
          borderRadius: 20,
          background: 'rgba(59,130,246,0.12)',
          border: '1px solid rgba(59,130,246,0.3)',
          marginBottom: '0.85rem',
        }}>
          <Send size={13} color="#3b82f6" />
          <span style={{ fontSize: '0.74rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: '#60a5fa' }}>
            Multi-Platform Engine
          </span>
        </div>

        <h2 style={{
          fontSize: '2.1rem',
          fontWeight: 900,
          color: '#fff',
          letterSpacing: '-0.03em',
          margin: '0 0 0.5rem',
          lineHeight: 1.15,
        }}>
          One click. Every platform, natively.
        </h2>

        <p style={{
          fontSize: '0.92rem',
          color: '#94a3b8',
          margin: 0,
          lineHeight: 1.5,
        }}>
          The same ship line, rewritten for how each platform actually reads — not copy-pasted three times.
        </p>
      </div>

      {/* Input Form Bar */}
      <form
        onSubmit={handleGenerate}
        style={{
          maxWidth: 620,
          margin: '0 auto 2.5rem',
          display: 'flex',
          alignItems: 'center',
          background: '#111622',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 14,
          padding: '0.4rem 0.5rem 0.4rem 1rem',
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}
      >
        <span style={{ color: '#3b82f6', fontWeight: 900, fontSize: '1rem', marginRight: '0.6rem' }}>&gt;</span>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Paste an idea, a ship line, a post, or a product URL..."
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#fff',
            fontSize: '0.92rem',
            fontFamily: 'monospace, sans-serif',
          }}
        />
        <button
          type="submit"
          disabled={generating}
          className="btn btn-primary"
          style={{
            background: '#2563eb',
            color: '#fff',
            fontWeight: 800,
            fontSize: '0.84rem',
            padding: '0.55rem 1.15rem',
            borderRadius: 10,
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          {generating ? <RefreshCw className="spin" size={14} /> : null}
          {generating ? 'Rewriting...' : 'Generate'}
        </button>
      </form>

      {/* 3 Native Platform Cards (X, LinkedIn, Reddit) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '1.25rem',
        alignItems: 'stretch',
      }}>
        
        {/* CARD 1: X (TWITTER) NATIVE CARD */}
        <div style={{
          background: '#000000',
          borderRadius: 16,
          border: '1px solid rgba(255,255,255,0.12)',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}>
          <div>
            {/* Author Row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.85rem' }}>
              <div style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                background: '#2563eb',
                color: '#fff',
                fontWeight: 800,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {initials}
              </div>
              <div style={{ lineHeight: 1.2 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                  <span style={{ fontWeight: 800, color: '#fff', fontSize: '0.88rem' }}>{bundle?.x_post?.display_name || businessName}</span>
                  <span style={{ color: '#3b82f6', fontSize: '0.75rem' }}>●</span>
                </div>
                <span style={{ fontSize: '0.74rem', color: '#71717a' }}>{bundle?.x_post?.handle || '@founder'} · 2h</span>
              </div>
            </div>

            {/* Post Content */}
            <p style={{
              fontSize: '0.84rem',
              color: '#e4e4e7',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              margin: '0 0 1rem',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
            }}>
              {bundle?.x_post?.content}
            </p>
          </div>

          <div>
            {/* Metric Footer */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '0.75rem',
              borderTop: '1px solid rgba(255,255,255,0.08)',
              fontSize: '0.74rem',
              color: '#71717a',
              marginBottom: '0.75rem',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><MessageSquare size={13} /> {bundle?.x_post?.metrics_estimate?.replies || '12'}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><Repeat size={13} /> {bundle?.x_post?.metrics_estimate?.retweets || '48'}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><Heart size={13} color="#f43f5e" /> {bundle?.x_post?.metrics_estimate?.likes || '310'}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}><BarChart2 size={13} /> {bundle?.x_post?.metrics_estimate?.views || '21K'}</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.74rem', color: '#38bdf8', fontWeight: 700 }}>
                ● Show this thread — 6 posts
              </span>
              <button
                onClick={() => copyText(bundle?.x_post?.content || '', 'X Post')}
                className="btn"
                style={{ background: 'rgba(255,255,255,0.08)', color: '#fff', fontSize: '0.72rem', fontWeight: 700, padding: '0.25rem 0.6rem', border: '1px solid rgba(255,255,255,0.1)' }}
              >
                <Copy size={11} style={{ display: 'inline', marginRight: 3 }} /> Copy for X
              </button>
            </div>
          </div>
        </div>

        {/* CARD 2: LINKEDIN NATIVE CARD */}
        <div style={{
          background: '#ffffff',
          borderRadius: 16,
          border: '1px solid rgba(255,255,255,0.12)',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
          color: '#18181b',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}>
          <div>
            {/* Author Row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.85rem' }}>
              <div style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                background: '#0a66c2',
                color: '#fff',
                fontWeight: 800,
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {initials}
              </div>
              <div style={{ lineHeight: 1.2 }}>
                <div style={{ fontWeight: 800, color: '#000', fontSize: '0.88rem' }}>
                  {bundle?.linkedin_post?.author_name || businessName} <span style={{ color: '#64748b', fontSize: '0.74rem' }}>· 1st</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{bundle?.linkedin_post?.headline || 'Founder & Builder'}</div>
                <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>now · 🌐</span>
              </div>
            </div>

            {/* Post Content */}
            <p style={{
              fontSize: '0.82rem',
              color: '#1e293b',
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              margin: '0 0 1rem',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
            }}>
              {bundle?.linkedin_post?.content}
            </p>
          </div>

          <div>
            {/* Metric Footer */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              paddingTop: '0.65rem',
              borderTop: '1px solid #e2e8f0',
              fontSize: '0.74rem',
              color: '#64748b',
              marginBottom: '0.75rem',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                👍❤️💡 {bundle?.linkedin_post?.metrics_estimate?.reactions || '47'} reactions
              </span>
              <span>{bundle?.linkedin_post?.metrics_estimate?.comments || '6'} comments</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', color: '#0a66c2', fontWeight: 800 }}>
                💼 Story Insight
              </span>
              <button
                onClick={() => copyText(bundle?.linkedin_post?.content || '', 'LinkedIn Post')}
                className="btn"
                style={{ background: '#0a66c2', color: '#fff', fontSize: '0.72rem', fontWeight: 700, padding: '0.25rem 0.6rem', border: 'none' }}
              >
                <Copy size={11} style={{ display: 'inline', marginRight: 3 }} /> Copy for LinkedIn
              </button>
            </div>
          </div>
        </div>

        {/* CARD 3: REDDIT NATIVE CARD */}
        <div style={{
          background: '#1a1a1b',
          borderRadius: 16,
          border: '1px solid rgba(255,255,255,0.12)',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'relative',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}>
          <div>
            {/* Subreddit Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <div style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: '#ff4500',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
              }}>
                🤖
              </div>
              <span style={{ fontWeight: 800, color: '#fff', fontSize: '0.82rem' }}>
                {bundle?.reddit_post?.subreddit || 'r/SideProject'}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#71717a' }}>· 5h</span>
            </div>

            {/* Reddit Title */}
            <h4 style={{
              margin: '0 0 0.65rem',
              fontSize: '0.9rem',
              fontWeight: 800,
              color: '#fff',
              lineHeight: 1.35,
            }}>
              {bundle?.reddit_post?.title}
            </h4>

            {/* Reddit Body */}
            <p style={{
              fontSize: '0.8rem',
              color: '#d4d4d8',
              lineHeight: 1.45,
              whiteSpace: 'pre-wrap',
              margin: '0 0 1rem',
            }}>
              {bundle?.reddit_post?.body}
            </p>
          </div>

          <div>
            {/* Metric Footer */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              paddingTop: '0.65rem',
              borderTop: '1px solid rgba(255,255,255,0.08)',
              fontSize: '0.74rem',
              color: '#a1a1aa',
              marginBottom: '0.75rem',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', background: 'rgba(255,255,255,0.06)', padding: '0.2rem 0.5rem', borderRadius: 12 }}>
                <ArrowUp size={13} color="#ff4500" /> {bundle?.reddit_post?.metrics_estimate?.upvotes || '248'}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <MessageSquare size={13} /> {bundle?.reddit_post?.metrics_estimate?.comments || '32'}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <Share2 size={13} /> Share
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', color: '#ff4500', fontWeight: 800 }}>
                🤖 Authentic Builder Post
              </span>
              <button
                onClick={() => {
                  const block = `${bundle?.reddit_post?.title}\n\n${bundle?.reddit_post?.body}`;
                  copyText(block, 'Reddit Post');
                }}
                className="btn"
                style={{ background: '#ff4500', color: '#fff', fontSize: '0.72rem', fontWeight: 700, padding: '0.25rem 0.6rem', border: 'none' }}
              >
                <Copy size={11} style={{ display: 'inline', marginRight: 3 }} /> Copy for Reddit
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
