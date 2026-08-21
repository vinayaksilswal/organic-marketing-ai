import React, { useEffect, useRef, useState } from 'react';

/**
 * A single row of cards that slides forever.
 *
 * Six cards in a four-wide grid wrap to a row of four and an orphaned row of
 * two, which reads as an unfinished section rather than a set. A rail keeps
 * one clean line and brings the other two round on rotation, so every card is
 * seen and the row is never ragged.
 *
 * The loop is seamless because the first `visible` cards are repeated at the
 * end: the rail slides into the copies, then jumps back to the start with the
 * transition switched off, which is invisible because the frames are
 * identical.
 *
 * Pauses on hover and on focus, so nobody loses a card they are reading or
 * tabbing through, and holds still entirely for anyone who has asked the
 * system to reduce motion.
 */
const GAP = 22;

const breakpointVisible = (width) => {
  if (width < 640) return 1;
  if (width < 920) return 2;
  if (width < 1180) return 3;
  return 4;
};

const CardRail = ({ items, renderItem, interval = 3400 }) => {
  const [visible, setVisible] = useState(() =>
    breakpointVisible(typeof window === 'undefined' ? 1280 : window.innerWidth)
  );
  const [index, setIndex] = useState(0);
  const [animate, setAnimate] = useState(true);
  const paused = useRef(false);

  useEffect(() => {
    const onResize = () => setVisible(breakpointVisible(window.innerWidth));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const total = items.length;
  const canSlide = total > visible;

  // Someone who has asked for reduced motion gets a static, readable row
  // rather than movement they did not want.
  const stillness =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  useEffect(() => {
    if (!canSlide || stillness) return undefined;
    const timer = setInterval(() => {
      if (!paused.current) setIndex((i) => i + 1);
    }, interval);
    return () => clearInterval(timer);
  }, [canSlide, stillness, interval]);

  // Once the rail has slid into the repeated head, snap back without a
  // transition. The two frames show the same cards, so nothing is visible.
  useEffect(() => {
    if (index < total) {
      if (!animate) {
        const t = setTimeout(() => setAnimate(true), 30);
        return () => clearTimeout(t);
      }
      return undefined;
    }
    const t = setTimeout(() => {
      setAnimate(false);
      setIndex(0);
    }, 620);
    return () => clearTimeout(t);
  }, [index, total, animate]);

  // Index is clamped so a resize that raises `visible` cannot leave the rail
  // scrolled past its own contents.
  useEffect(() => {
    if (index > total) setIndex(0);
  }, [visible, index, total]);

  const loop = canSlide && !stillness ? [...items, ...items.slice(0, visible)] : items;

  // 100% is the rail's width, so (100% + GAP) / visible is exactly one card
  // plus one gap — the distance of a single step, whatever the breakpoint.
  const shift = canSlide && !stillness
    ? `translateX(calc(-1 * ${index} * (100% + ${GAP}px) / ${visible}))`
    : 'none';

  // A rail that only moves on its own timer asks the reader to wait for the
  // card they want. The arrows let them go and get it. Backwards from the
  // first card wraps to the last: an endless rail with a dead end on one side
  // is just a list that moves.
  const nudge = (dir) => {
    setAnimate(true);
    setIndex((i) => (i + dir < 0 ? total - 1 : i + dir));
  };

  const arrow = (side) => ({
    position: 'absolute',
    top: 'calc(50% - 1.6rem)',
    [side]: -6,
    transform: 'translateY(-50%)',
    zIndex: 3,
    width: 44,
    height: 44,
    borderRadius: 999,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    background: 'rgba(255,255,255,0.92)',
    border: '1px solid rgba(11,16,32,0.10)',
    boxShadow: '0 2px 6px rgba(11,16,32,0.08), 0 10px 24px -10px rgba(11,16,32,0.22)',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
    color: '#0b1020',
    padding: 0,
    lineHeight: 0,
  });

  return (
    <div
      style={{ position: 'relative', width: '100%' }}
      onMouseEnter={() => { paused.current = true; }}
      onMouseLeave={() => { paused.current = false; }}
      onFocusCapture={() => { paused.current = true; }}
      onBlurCapture={() => { paused.current = false; }}
    >
      {canSlide && (
        <>
          <button type="button" aria-label="Previous cards"
                  onClick={() => nudge(-1)} style={arrow('left')}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" strokeWidth="2.4"
                 strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <button type="button" aria-label="Next cards"
                  onClick={() => nudge(1)} style={arrow('right')}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" strokeWidth="2.4"
                 strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </>
      )}

      <div style={{ overflow: 'hidden', width: '100%' }}>
      <div
        style={{
          display: 'flex',
          gap: `${GAP}px`,
          transform: shift,
          transition: animate ? 'transform .62s cubic-bezier(.4,0,.2,1)' : 'none',
          willChange: 'transform',
        }}
      >
        {loop.map((item, i) => (
          <div
            key={`${item.key ?? i}-${i}`}
            style={{
              flex: `0 0 calc((100% - ${GAP * (visible - 1)}px) / ${visible})`,
              minWidth: 0,
            }}
          >
            {renderItem(item)}
          </div>
        ))}
        </div>
      </div>

      {canSlide && !stillness && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 0, marginTop: '1.2rem' }}>
          {items.map((item, i) => (
            <button
              key={item.key ?? i}
              aria-label={`Show card ${i + 1}`}
              onClick={() => setIndex(i)}
              style={{
                // The tap target is 44px; the dot inside stays 7px. A control
                // sized to its own artwork is 7px tall, which is unhittable on
                // a phone -- and a dot that grew to 44px would read as a
                // button rather than an indicator. Padding separates the two.
                width: 30,
                height: 44,
                padding: 0,
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  display: 'block',
                  width: index % total === i ? 22 : 7,
                  height: 7,
                  borderRadius: 999,
                  background: index % total === i
                    ? 'var(--blue, #2563eb)'
                    : 'rgba(120,120,140,0.28)',
                  transition: 'width .35s ease, background .35s ease',
                }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default CardRail;
