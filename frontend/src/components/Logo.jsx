import React from 'react';

/**
 * The Organiflo mark.
 *
 * The supplied export was a .jpeg, which cannot carry an alpha channel — the
 * transparency checkerboard had been flattened into the picture as real grey
 * squares. scripts/make_logo_png.py keys it back out on chroma (the mark is
 * saturated neon, the checkerboard is pure grey where R=G=B) and writes the
 * two assets used here. The chroma ramp is what preserves the halo: a glow
 * pixel is grey blended with neon, so it lands between the thresholds and
 * gets a partial alpha instead of being cut off with a visible edge.
 *
 * The mark is the image; the word is live text. Baking the wordmark in as
 * pixels would go soft on retina, cost bytes on the page that must load
 * fastest, and could not inherit the heading face. This way the word is
 * selectable, searchable and sharp at any size.
 */
const Logo = ({ size = 30, showWordmark = false, tagline = false, style }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: size * 0.28, ...style }}>
    <img
      src="/logo-mark.png"
      alt="Organiflo"
      width={size}
      height={size}
      // Eager and high priority: this is above the fold on every page it
      // appears on, and a logo that pops in late is the first thing a visitor
      // sees go wrong.
      loading="eager"
      fetchpriority="high"
      style={{ width: size, height: size, display: 'block', flexShrink: 0, objectFit: 'contain' }}
    />

    {showWordmark && (
      <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.06 }}>
        <span
          style={{
            fontFamily: "'Bricolage Grotesque', system-ui, sans-serif",
            fontWeight: 800,
            fontSize: size * 0.66,
            letterSpacing: '-.03em',
            background: 'linear-gradient(100deg, #22d3ee, #3b82f6 46%, #a855f7)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            whiteSpace: 'nowrap',
          }}
        >
          Organiflo
        </span>
        {tagline && (
          <span style={{
            fontSize: size * 0.235,
            letterSpacing: '.015em',
            color: 'currentColor',
            opacity: 0.6,
            fontWeight: 500,
            whiteSpace: 'nowrap',
          }}>
            Your Organic Social Growth Engine
          </span>
        )}
      </span>
    )}
  </span>
);

export default Logo;
