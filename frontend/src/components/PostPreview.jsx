import React, { useState } from 'react';
import {
  Heart, MessageCircle, Send as SendIcon, Bookmark, MoreHorizontal, Globe,
  ThumbsUp, Repeat2, BarChart2, Play, Share2,
} from 'lucide-react';

/**
 * What the post will actually look like, on the platform it is going to.
 *
 * WHY THIS EXISTS
 * ---------------
 * Every platform cuts the caption in a different place, and the cut is what
 * decides whether anybody reads the second sentence. Instagram hides
 * everything past roughly 125 characters behind "more". X refuses anything
 * over 280 outright. LinkedIn collapses at about 210 on a phone. Writing a
 * caption without seeing that is writing blind, and the usual result is a
 * hook that lands three lines below the fold.
 *
 * So the fold is drawn. The greyed text is what a scroller will not see
 * unless they tap, and the counter says how much of it there is.
 *
 * NOT A SCREENSHOT
 * ----------------
 * This is an honest approximation, not a pixel-exact clone -- the platforms
 * change their own chrome monthly and chasing it would be a full-time job for
 * no gain. What is exact is the part that matters: the truncation points, the
 * aspect ratios, and whether media is required at all.
 */

// Where each platform stops showing the caption, and what it does about it.
// These are the numbers that change what somebody writes.
export const FOLD = {
  instagram: { at: 125, label: 'more', note: 'Instagram hides the rest behind "more".' },
  facebook: { at: 250, label: 'See more', note: 'Facebook collapses long posts.' },
  x: { at: 280, label: null, note: 'X will not accept anything over 280 characters.' },
  linkedin: { at: 210, label: '…see more', note: 'LinkedIn collapses at about 210 on a phone.' },
  youtube: { at: 100, label: null, note: 'Only the first 100 characters show above the fold.' },
};

const PLATFORMS = [
  { id: 'instagram', name: 'Instagram', needsMedia: true },
  { id: 'facebook', name: 'Facebook', needsMedia: false },
  { id: 'x', name: 'X', needsMedia: false },
  { id: 'linkedin', name: 'LinkedIn', needsMedia: false },
  { id: 'youtube', name: 'YouTube', needsMedia: 'video' },
];

const looksLikeVideo = (url = '') => /\.(mp4|mov|m4v|webm)(\?|$)/i.test(url);

function splitAtFold(text = '', platform) {
  const rule = FOLD[platform] || FOLD.facebook;
  const clean = (text || '').trim();
  if (clean.length <= rule.at) return { head: clean, tail: '', rule };
  // Break on a word so the preview does not cut mid-word, which no platform does.
  let cut = clean.lastIndexOf(' ', rule.at);
  if (cut < rule.at * 0.6) cut = rule.at;
  return { head: clean.slice(0, cut), tail: clean.slice(cut), rule };
}

const Avatar = ({ name = '', src, size = 34, square = false }) => (
  src ? (
    <img src={src} alt="" style={{
      width: size, height: size, borderRadius: square ? 6 : '50%',
      objectFit: 'cover', flexShrink: 0,
    }} />
  ) : (
    <div style={{
      width: size, height: size, borderRadius: square ? 6 : '50%', flexShrink: 0,
      background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))',
      color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 800, fontSize: size * 0.4,
    }}>
      {(name || '?').trim().charAt(0).toUpperCase()}
    </div>
  )
);

/** The caption, with everything below the fold greyed out. */
const Caption = ({ text, platform, style }) => {
  const { head, tail, rule } = splitAtFold(text, platform);
  const hashtag = (s) => s.split(/(#[A-Za-z0-9_]+)/g).map((part, i) =>
    part.startsWith('#')
      ? <span key={i} style={{ color: '#1d9bf0' }}>{part}</span>
      : <span key={i}>{part}</span>
  );

  return (
    <div style={{ fontSize: '0.82rem', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word', ...style }}>
      {hashtag(head)}
      {tail && (
        <>
          <span style={{ opacity: 0.35 }}>{hashtag(tail)}</span>
          {rule.label && (
            <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}> {rule.label}</span>
          )}
        </>
      )}
    </div>
  );
};

const Media = ({ urls = [], ratio = '4 / 5', fit = 'cover', radius = 0 }) => {
  const url = urls[0];
  if (!url) return null;
  const video = looksLikeVideo(url);
  return (
    <div style={{
      width: '100%', aspectRatio: ratio, background: '#000', borderRadius: radius,
      overflow: 'hidden', position: 'relative',
    }}>
      {video ? (
        <>
          <video src={url} style={{ width: '100%', height: '100%', objectFit: fit }} muted playsInline />
          <div style={{
            position: 'absolute', inset: 0, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: 46, height: 46, borderRadius: '50%', background: 'rgba(0,0,0,0.55)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Play size={20} color="#fff" fill="#fff" />
            </div>
          </div>
        </>
      ) : (
        <img src={url} alt="" style={{ width: '100%', height: '100%', objectFit: fit }} />
      )}
      {urls.length > 1 && (
        <div style={{
          position: 'absolute', top: 8, right: 8, background: 'rgba(0,0,0,0.6)',
          color: '#fff', fontSize: '0.68rem', fontWeight: 700,
          padding: '0.1rem 0.45rem', borderRadius: 999,
        }}>
          1/{urls.length}
        </div>
      )}
    </div>
  );
};

const Shell = ({ children, dark = false }) => (
  <div style={{
    border: '1px solid var(--border-color)', borderRadius: 12, overflow: 'hidden',
    background: dark ? '#000' : 'var(--bg-card)',
    color: dark ? '#e7e9ea' : 'var(--text-main)',
    maxWidth: 420, width: '100%',
  }}>
    {children}
  </div>
);

const Row = ({ children, style }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', padding: '0.7rem 0.8rem', ...style }}>
    {children}
  </div>
);

// ---------------------------------------------------------------------------
// One renderer per platform
// ---------------------------------------------------------------------------

const Instagram = ({ caption, media, name, handle, avatar }) => (
  <Shell>
    <Row>
      <Avatar name={name} src={avatar} size={32} />
      <strong style={{ fontSize: '0.82rem' }}>{handle || name}</strong>
      <MoreHorizontal size={16} style={{ marginLeft: 'auto', opacity: 0.5 }} />
    </Row>
    <Media urls={media} ratio="4 / 5" />
    <div style={{ padding: '0.6rem 0.8rem' }}>
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.5rem' }}>
        <Heart size={20} />
        <MessageCircle size={20} />
        <SendIcon size={20} />
        <Bookmark size={20} style={{ marginLeft: 'auto' }} />
      </div>
      <Caption text={caption} platform="instagram" />
    </div>
  </Shell>
);

const Facebook = ({ caption, media, name, avatar }) => (
  <Shell>
    <Row>
      <Avatar name={name} src={avatar} size={38} />
      <div>
        <div style={{ fontSize: '0.84rem', fontWeight: 700 }}>{name}</div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          Just now · <Globe size={10} />
        </div>
      </div>
    </Row>
    <div style={{ padding: '0 0.8rem 0.6rem' }}>
      <Caption text={caption} platform="facebook" />
    </div>
    <Media urls={media} ratio="1 / 1" />
    <div style={{
      display: 'flex', borderTop: '1px solid var(--border-color)',
      fontSize: '0.76rem', color: 'var(--text-muted)', fontWeight: 600,
    }}>
      {[[ThumbsUp, 'Like'], [MessageCircle, 'Comment'], [Share2, 'Share']].map(([Icon, label]) => (
        <div key={label} style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: '0.3rem', padding: '0.5rem',
        }}>
          <Icon size={15} /> {label}
        </div>
      ))}
    </div>
  </Shell>
);

const X = ({ caption, media, name, handle, avatar }) => {
  const over = (caption || '').trim().length > FOLD.x.at;
  return (
    <Shell dark>
      <div style={{ display: 'flex', gap: '0.65rem', padding: '0.8rem' }}>
        <Avatar name={name} src={avatar} size={38} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.82rem', marginBottom: '0.2rem' }}>
            <strong>{name}</strong>
            <span style={{ color: '#71767b' }}> {handle} · now</span>
          </div>
          {/* Over the limit is not a fold on X -- the post is refused. */}
          <Caption text={caption} platform="x" style={{ color: over ? '#f4212e' : undefined }} />
          {media?.length > 0 && (
            <div style={{ marginTop: '0.6rem' }}>
              <Media urls={media} ratio="16 / 9" radius={14} />
            </div>
          )}
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginTop: '0.7rem',
            color: '#71767b', maxWidth: 280,
          }}>
            <MessageCircle size={16} /><Repeat2 size={16} /><Heart size={16} /><BarChart2 size={16} />
          </div>
        </div>
      </div>
    </Shell>
  );
};

const LinkedIn = ({ caption, media, name, avatar, headline }) => (
  <Shell>
    <Row style={{ alignItems: 'flex-start' }}>
      <Avatar name={name} src={avatar} size={40} square />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.84rem', fontWeight: 700 }}>{name}</div>
        <div style={{
          fontSize: '0.7rem', color: 'var(--text-muted)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {headline || 'Business'}
        </div>
        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          now · <Globe size={10} />
        </div>
      </div>
    </Row>
    <div style={{ padding: '0 0.8rem 0.6rem' }}>
      <Caption text={caption} platform="linkedin" />
    </div>
    <Media urls={media} ratio="1.91 / 1" />
    <div style={{
      display: 'flex', borderTop: '1px solid var(--border-color)',
      fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600,
    }}>
      {[[ThumbsUp, 'Like'], [MessageCircle, 'Comment'], [Repeat2, 'Repost'], [SendIcon, 'Send']].map(([Icon, label]) => (
        <div key={label} style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          gap: '0.25rem', padding: '0.5rem',
        }}>
          <Icon size={14} /> {label}
        </div>
      ))}
    </div>
  </Shell>
);

const YouTube = ({ caption, media, name, avatar }) => {
  const video = (media || []).find(looksLikeVideo);
  const title = (caption || '').split('\n')[0];
  return (
    <Shell>
      <Media urls={video ? [video] : media} ratio="9 / 16" fit="cover" />
      <Row style={{ alignItems: 'flex-start' }}>
        <Avatar name={name} src={avatar} size={34} />
        <div style={{ minWidth: 0 }}>
          {/* YouTube shows the first line as the title. A caption written as
              one paragraph becomes a title nobody can read. */}
          <div style={{
            fontSize: '0.84rem', fontWeight: 700, lineHeight: 1.35,
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}>
            {title.slice(0, FOLD.youtube.at)}
            {title.length > FOLD.youtube.at && (
              <span style={{ opacity: 0.35 }}>{title.slice(FOLD.youtube.at)}</span>
            )}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            {name} · No views · now
          </div>
        </div>
      </Row>
    </Shell>
  );
};

const RENDERERS = { instagram: Instagram, facebook: Facebook, x: X, linkedin: LinkedIn, youtube: YouTube };

/**
 * @param caption   the text going out
 * @param media     array of URLs
 * @param platforms which tabs to offer (defaults to all)
 * @param business  { name, handle, avatar, headline }
 */
export default function PostPreview({
  caption = '', media = [], platforms, business = {}, defaultPlatform,
}) {
  const available = PLATFORMS.filter((p) => !platforms || platforms.includes(p.id));
  const [active, setActive] = useState(defaultPlatform || available[0]?.id || 'instagram');

  const current = available.find((p) => p.id === active) || available[0];
  if (!current) return null;

  const Renderer = RENDERERS[current.id];
  const len = (caption || '').trim().length;
  const rule = FOLD[current.id];
  const hidden = Math.max(0, len - rule.at);

  // What this platform cannot accept, said before the post is scheduled
  // rather than discovered in an error log four hours later.
  let blocker = null;
  if (current.needsMedia === true && media.length === 0) {
    blocker = 'Instagram cannot publish without an image or video.';
  } else if (current.needsMedia === 'video' && !media.some(looksLikeVideo)) {
    blocker = 'YouTube needs a video. This post will be skipped there.';
  } else if (current.id === 'x' && len > FOLD.x.at) {
    blocker = `${len - FOLD.x.at} characters over the 280 limit — X will refuse this.`;
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.85rem' }}>
        {available.map((p) => (
          <button
            key={p.id}
            onClick={() => setActive(p.id)}
            style={{
              minHeight: 34, padding: '0 0.7rem', borderRadius: 8, cursor: 'pointer',
              fontSize: '0.78rem', fontWeight: 700,
              background: active === p.id ? 'var(--primary-color)' : 'transparent',
              color: active === p.id ? '#fff' : 'var(--text-muted)',
              border: `1px solid ${active === p.id ? 'var(--primary-color)' : 'var(--border-color)'}`,
            }}
          >
            {p.name}
          </button>
        ))}
      </div>

      <Renderer
        caption={caption}
        media={media}
        name={business.name || 'Your business'}
        handle={business.handle || '@yourbusiness'}
        avatar={business.avatar}
        headline={business.headline}
      />

      <div style={{ marginTop: '0.7rem', maxWidth: 420 }}>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
          {len} characters. {rule.note}
          {hidden > 0 && current.id !== 'x' && (
            <> <strong>{hidden}</strong> of them are below the fold.</>
          )}
        </div>
        {blocker && (
          <div style={{
            marginTop: '0.45rem', fontSize: '0.76rem', fontWeight: 600,
            color: '#f59e0b', background: 'rgba(245,158,11,0.08)',
            border: '1px solid rgba(245,158,11,0.25)', borderRadius: 8,
            padding: '0.45rem 0.6rem', lineHeight: 1.45,
          }}>
            {blocker}
          </div>
        )}
      </div>
    </div>
  );
}
