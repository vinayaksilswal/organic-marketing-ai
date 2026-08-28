import React, { useCallback, useEffect, useState } from 'react';
import { Newspaper, RefreshCw, Copy, Check, Send, ExternalLink } from 'lucide-react';
import { API_BASE, authFetch, apiError } from '../config';
import PostPreview from './PostPreview';

/**
 * Daily LinkedIn posts, from this week's industry news.
 *
 * WHY
 * ---
 * A business account that only talks about itself runs out of material by
 * week three, and every post after that gets a little more promotional. This
 * gives it a reason to post every day that is not "buy our thing".
 *
 * The source is always shown. A take with no visible story behind it reads as
 * an opinion from nowhere, and the customer needs to be able to check that
 * the post is about something real before it goes out under their name.
 */

const ANGLES = [
  'Agree, then add what it missed',
  'Take the opposite view',
  'What it means for the reader',
  'Something to act on this week',
  'Connect it to a longer trend',
];

export default function NewsPosts({ token, activeWorkspaceId, showToast, business }) {
  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [angle, setAngle] = useState(2);
  const [writing, setWriting] = useState(null);
  const [post, setPost] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (!activeWorkspaceId) return;
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/creatives/news`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiError(body, 'Could not load industry news.'));
      setStories(body.stories || []);
      setQuery(body.query || '');
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      setLoading(false);
    }
  }, [activeWorkspaceId, token, showToast]);

  useEffect(() => { load(); }, [load]);

  const write = async (story, queue = false) => {
    setWriting(story.title);
    setPost(null);
    try {
      const res = await authFetch(`${API_BASE}/creatives/news-post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          title: story.title, source: story.source, link: story.link,
          angle, schedule_to_queue: queue,
        }),
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiError(body, 'Could not write that post.'));
      setPost(body);
      // Says what actually happened. If LinkedIn is not connected nothing was
      // queued, and claiming otherwise is the lie this codebase keeps fixing.
      if (queue) {
        showToast?.(body.queued
          ? 'Queued to LinkedIn — it goes out shortly.'
          : 'Written, but not queued: connect LinkedIn first.', !body.queued);
      }
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      setWriting(null);
    }
  };

  return (
    <div style={{
      padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 14,
      border: '1px solid var(--border-color)', marginBottom: '2rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
        <Newspaper size={18} color="var(--primary-color)" />
        <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Post about this week's news</h2>
        <button
          onClick={load}
          disabled={loading}
          className="btn btn-secondary"
          style={{ marginLeft: 'auto', minHeight: 34, fontSize: '0.78rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
        >
          <RefreshCw size={13} style={loading ? { animation: 'spin 1s linear infinite' } : undefined} />
          Refresh
        </button>
      </div>

      <p style={{ margin: '0 0 1rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
        LinkedIn rewards a short, opinionated take on something that just
        happened. These are this week's stories in your industry
        {query && <> — searched for <strong>{query}</strong></>}.
        Stories you have already posted about are left out.
      </p>

      <div style={{ marginBottom: '1rem' }}>
        <label style={{
          fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-muted)',
          textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem',
        }}>Your angle</label>
        <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
          {ANGLES.map((label, i) => (
            <button
              key={label}
              onClick={() => setAngle(i)}
              style={{
                minHeight: 32, padding: '0 0.6rem', borderRadius: 8, cursor: 'pointer',
                fontSize: '0.74rem', fontWeight: 700,
                background: angle === i ? 'var(--primary-color)' : 'transparent',
                color: angle === i ? '#fff' : 'var(--text-muted)',
                border: `1px solid ${angle === i ? 'var(--primary-color)' : 'var(--border-color)'}`,
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Reading the news…</p>}

      {!loading && stories.length === 0 && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Nothing new in your industry this week. Try again tomorrow, or widen
          the industry on your business profile.
        </p>
      )}

      <div style={{ display: 'grid', gap: '0.5rem' }}>
        {stories.map((s) => (
          <div key={s.title} style={{
            border: '1px solid var(--border-color)', borderRadius: 10,
            padding: '0.75rem 0.9rem', display: 'flex', alignItems: 'center',
            gap: '0.75rem', flexWrap: 'wrap',
          }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: '0.86rem', fontWeight: 600, lineHeight: 1.4 }}>{s.title}</div>
              <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                {s.source}
                {s.published && <>· {new Date(s.published).toLocaleDateString()}</>}
                {s.link && (
                  <a href={s.link} target="_blank" rel="noopener noreferrer"
                     style={{ color: 'var(--secondary-color)', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                    <ExternalLink size={11} /> read
                  </a>
                )}
              </div>
            </div>
            <button
              onClick={() => write(s, false)}
              disabled={!!writing}
              className="btn btn-secondary"
              style={{ minHeight: 34, fontSize: '0.76rem', fontWeight: 700 }}
            >
              {writing === s.title ? 'Writing…' : 'Write a post'}
            </button>
            <button
              onClick={() => write(s, true)}
              disabled={!!writing}
              className="btn btn-primary"
              style={{ minHeight: 34, fontSize: '0.76rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
            >
              <Send size={13} /> Write &amp; queue
            </button>
          </div>
        ))}
      </div>

      {post && (
        <div style={{ marginTop: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: '0.9rem' }}>Reacting to:</strong>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              {post.source_title} ({post.source_name})
            </span>
            <button
              onClick={() => {
                navigator.clipboard?.writeText(post.content || '');
                setCopied(true);
                setTimeout(() => setCopied(false), 1600);
              }}
              className="btn btn-secondary"
              style={{ marginLeft: 'auto', minHeight: 32, fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
            >
              {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
            </button>
          </div>

          {/* Shown as LinkedIn will show it, fold and all. */}
          <PostPreview
            caption={post.content}
            media={[]}
            platforms={['linkedin']}
            business={{ name: business?.name || 'Your business', headline: business?.industry }}
          />
        </div>
      )}
    </div>
  );
}
