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

  return (
    <div
      style={{ overflow: 'hidden', width: '100%' }}
      onMouseEnter={() => { paused.current = true; }}
      onMouseLeave={() => { paused.current = false; }}
      onFocusCapture={() => { paused.current = true; }}
      onBlurCapture={() => { paused.current = false; }}
    >
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

      {canSlide && !stillness && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 7, marginTop: '1.6rem' }}>
          {items.map((item, i) => (
            <button
              key={item.key ?? i}
              aria-label={`Show card ${i + 1}`}
              onClick={() => setIndex(i)}
              style={{
                width: index % total === i ? 22 : 7,
                height: 7,
                borderRadius: 99,
                border: 'none',
                padding: 0,
                cursor: 'pointer',
                background: index % total === i
                  ? 'var(--blue, #2563eb)'
                  : 'rgba(120,120,140,0.28)',
                transition: 'width .35s ease, background .35s ease',
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default CardRail;
