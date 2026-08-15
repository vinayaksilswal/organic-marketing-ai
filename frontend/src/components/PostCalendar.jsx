import React, { useMemo, useState } from 'react';
import {
  ChevronLeft, ChevronRight, Facebook, Instagram, Clock,
  CheckCircle2, XCircle, FileText, Film,
} from 'lucide-react';

/**
 * The posting schedule as a month, with every post on the day it went out.
 *
 * A reverse-chronological list answers "what happened last?" but not the
 * questions an operator actually has: is anything going out tomorrow, did
 * Tuesday publish, why is there a gap. Those are shape questions, and a
 * calendar is the shape.
 *
 * Each day carries its posts as thumbnails with a status ring, so the month
 * reads at a glance: solid green means it ran, red means it did not, and an
 * empty cell is a day nothing went out — which is the most useful thing on
 * the grid and the hardest to see in a list.
 */

const STATUS = {
  POSTED:    { label: 'Published', colour: '#10b981', Icon: CheckCircle2 },
  FAILED:    { label: 'Failed',    colour: '#ef4444', Icon: XCircle },
  DRAFT:     { label: 'Draft',     colour: '#f59e0b', Icon: FileText },
  SCHEDULED: { label: 'Scheduled', colour: '#3b82f6', Icon: Clock },
};

const statusOf = (post) => STATUS[post.status] || STATUS.SCHEDULED;

const isVideo = (url) =>
  typeof url === 'string' && url.split('?')[0].toLowerCase().match(/\.(mp4|mov|webm|m4v)$/);

// A post belongs on the day it actually went out; a post that never went out
// belongs on the day it was meant to.
const dayKeyOf = (post) => {
  const when = post.postedAt || post.scheduledAt || post.createdAt;
  if (!when) return null;
  const d = new Date(when);
  if (Number.isNaN(d.getTime())) return null;
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
};

const timeOf = (post) => {
  const when = post.postedAt || post.scheduledAt || post.createdAt;
  if (!when) return '';
  const d = new Date(when);
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const Thumb = ({ post, size = 30 }) => {
  const url = (post.mediaUrls || [])[0];
  const { colour } = statusOf(post);
  const base = {
    width: size, height: size, borderRadius: 7, objectFit: 'cover',
    display: 'block', background: '#0d0d12',
    border: `1.5px solid ${colour}`, flexShrink: 0,
  };
  if (!url) {
    return (
      <div style={{ ...base, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <FileText size={size * 0.42} color={colour} />
      </div>
    );
  }
  if (isVideo(url)) {
    return (
      <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
        <video src={url} style={base} muted playsInline preload="metadata" />
        <Film size={11} color="#fff" style={{
          position: 'absolute', right: 2, bottom: 2,
          filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.9))',
        }} />
      </div>
    );
  }
  return <img src={url} alt="" loading="lazy" style={base} />;
};

const PostCalendar = ({ posts = [], onSelect }) => {
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  });

  const byDay = useMemo(() => {
    const map = new Map();
    posts.forEach((p) => {
      const key = dayKeyOf(p);
      if (!key) return;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(p);
    });
    // Earliest first inside a day, so the column reads down the clock.
    map.forEach((list) => list.sort((a, b) =>
      new Date(a.postedAt || a.scheduledAt || a.createdAt) -
      new Date(b.postedAt || b.scheduledAt || b.createdAt)
    ));
    return map;
  }, [posts]);

  const cells = useMemo(() => {
    const first = new Date(cursor.year, cursor.month, 1);
    const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate();
    const lead = first.getDay();
    const out = [];
    for (let i = 0; i < lead; i += 1) out.push(null);
    for (let d = 1; d <= daysInMonth; d += 1) out.push(d);
    return out;
  }, [cursor]);

  const monthPosts = useMemo(
    () => posts.filter((p) => {
      const when = p.postedAt || p.scheduledAt || p.createdAt;
      if (!when) return false;
      const d = new Date(when);
      return d.getFullYear() === cursor.year && d.getMonth() === cursor.month;
    }),
    [posts, cursor]
  );

  const tally = useMemo(() => {
    const t = { POSTED: 0, FAILED: 0, DRAFT: 0, SCHEDULED: 0 };
    monthPosts.forEach((p) => { t[p.status] = (t[p.status] || 0) + 1; });
    return t;
  }, [monthPosts]);

  const today = new Date();
  const isToday = (d) =>
    d && today.getFullYear() === cursor.year &&
    today.getMonth() === cursor.month && today.getDate() === d;

  const shift = (by) => setCursor((c) => {
    const m = c.month + by;
    if (m < 0) return { year: c.year - 1, month: 11 };
    if (m > 11) return { year: c.year + 1, month: 0 };
    return { ...c, month: m };
  });

  const monthName = new Date(cursor.year, cursor.month, 1)
    .toLocaleString([], { month: 'long', year: 'numeric' });

  const cellStyle = {
    minHeight: 104, borderRadius: 10, padding: '0.45rem',
    background: 'var(--cal-cell, rgba(0,0,0,0.02))',
    border: '1px solid var(--border-color)',
    display: 'flex', flexDirection: 'column', gap: '0.3rem',
    // A grid item's default min-width is auto, meaning it refuses to shrink
    // below its content. The post chips carry a 26px thumbnail plus text, so
    // seven columns of them were wider than the panel and the last day was
    // pushed off the right edge. Zero lets the track do its job.
    minWidth: 0,
    overflow: 'hidden',
  };

  return (
    <div className="cal-scroll">
      {/* Month bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '0.75rem',
        flexWrap: 'wrap', marginBottom: '1rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button onClick={() => shift(-1)} aria-label="Previous month"
            style={navBtn}><ChevronLeft size={16} /></button>
          <button onClick={() => shift(1)} aria-label="Next month"
            style={navBtn}><ChevronRight size={16} /></button>
        </div>
        <h3 style={{ margin: 0, fontSize: '1.1rem', minWidth: 190 }}>{monthName}</h3>
        <button
          onClick={() => setCursor({ year: today.getFullYear(), month: today.getMonth() })}
          style={{ ...navBtn, width: 'auto', padding: '0 0.75rem', fontSize: '0.8rem' }}>
          Today
        </button>

        <div style={{ display: 'flex', gap: '0.9rem', marginLeft: 'auto', flexWrap: 'wrap' }}>
          {Object.entries(STATUS).map(([key, { label, colour }]) => (
            tally[key] ? (
              <span key={key} style={{
                display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                fontSize: '0.78rem', color: 'var(--text-muted)',
              }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: colour }} />
                {tally[key]} {label.toLowerCase()}
              </span>
            ) : null
          ))}
        </div>
      </div>

      {/* Day-of-week header */}
      <div className="cal-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: '0.4rem', marginBottom: '0.4rem' }}>
        {DAY_LABELS.map((d) => (
          <div key={d} style={{
            textAlign: 'center', fontSize: '0.72rem', fontWeight: 700,
            letterSpacing: '.08em', color: 'var(--text-muted)', padding: '0.3rem 0',
          }}>{d}</div>
        ))}
      </div>

      {/* Grid */}
      <div className="cal-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: '0.4rem', width: '100%' }}>
        {cells.map((day, i) => {
          if (!day) return <div key={`pad-${i}`} style={{ ...cellStyle, background: 'transparent', border: '1px solid transparent' }} />;
          const key = `${cursor.year}-${cursor.month}-${day}`;
          const dayPosts = byDay.get(key) || [];
          const highlight = isToday(day);
          return (
            <div key={key} style={{
              ...cellStyle,
              border: highlight ? '1px solid rgba(139,92,246,0.55)' : cellStyle.border,
              background: highlight ? 'rgba(139,92,246,0.07)' : cellStyle.background,
            }}>
              <div style={{
                fontSize: '0.75rem', fontWeight: highlight ? 800 : 600,
                color: highlight ? '#c4b5fd' : 'var(--text-muted)',
              }}>{day}</div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', overflow: 'hidden' }}>
                {dayPosts.slice(0, 3).map((p) => {
                  const { colour, label } = statusOf(p);
                  return (
                    <button
                      key={p.id}
                      onClick={() => onSelect && onSelect(p)}
                      title={`${label} · ${timeOf(p)} · ${(p.caption || '').slice(0, 80)}`}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '0.35rem',
                        background: 'rgba(11, 16, 32, 0.03)', border: '1px solid rgba(11, 16, 32, 0.06)',
                        borderRadius: 8, padding: '0.18rem', cursor: 'pointer', width: '100%',
                        textAlign: 'left',
                      }}
                    >
                      <Thumb post={p} size={26} />
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span style={{
                          display: 'block', fontSize: '0.66rem', color: colour,
                          fontWeight: 700, lineHeight: 1.2,
                        }}>{timeOf(p)}</span>
                        <span style={{
                          display: 'block', fontSize: '0.62rem', color: 'var(--text-muted)',
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>{(p.caption || 'No caption').slice(0, 22)}</span>
                      </span>
                    </button>
                  );
                })}
                {dayPosts.length > 3 && (
                  <button
                    onClick={() => onSelect && onSelect(dayPosts[3])}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer', padding: 0,
                      fontSize: '0.65rem', color: 'var(--primary-color)', textAlign: 'left',
                    }}>
                    +{dayPosts.length - 3} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {monthPosts.length === 0 && (
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '1.5rem' }}>
          Nothing published in {monthName}.
        </p>
      )}
    </div>
  );
};

const navBtn = {
  width: 32, height: 32, borderRadius: 9, cursor: 'pointer',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  background: 'rgba(11, 16, 32, 0.05)',
  border: '1px solid var(--border-color)',
  color: 'var(--text-main)',
};

export { STATUS, statusOf, timeOf, Thumb, isVideo };
export default PostCalendar;
