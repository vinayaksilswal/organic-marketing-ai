import React from 'react';

/**
 * The Organiflo lockup: the mark as artwork, the words as live text.
 *
 * WHY THE WORDS ARE NOT PART OF THE IMAGE.
 *
 * The supplied logo was a .jpeg — lossy, with the transparency checkerboard
 * already flattened into it as grey squares. scripts/make_logo_png.py keys
 * that back out on chroma, but JPEG compression leaves artefacts along every
 * high-contrast edge, and those artefacts survive as a soft dark fringe in
 * the alpha. Against the near-black sidebar it is invisible. Against a white
 * page it reads as grime, and the type looks blurred — "low quality" is
 * exactly right, and no amount of re-keying fixes a lossy source.
 *
 * Type does not have that problem. Rendered as text, "Organiflo" is vector
 * sharp at any size and on any ground, costs no bytes, and inherits the
 * heading face so it belongs to the rest of the page. Only the mark, which
 * genuinely is artwork, stays an image.
 *
 * The gradient runs cyan through blue to violet, sampled from the original
 * so the words still match the mark beside them.
 *
 * If a lossless export ever arrives — PNG with real alpha, or SVG — the mark
 * gets sharper for free and none of this needs revisiting.
 */
// Below this the tagline cannot be set at a legible size, so it is not set
// at all. A line of 9px type is not a small version of a message; it is
// decoration that costs vertical space and says nothing.
const TAGLINE_MIN_SIZE = 42;

// noTagline is accepted because a call site already passed it. The prop was
// named `tagline`, so `noTagline` landed in nothing and the dashboard top bar
// rendered a 6px strapline nobody asked for.
const Logo = ({ size = 30, showWordmark = false, tagline = true, noTagline = false, style }) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: size * 0.26,
      ...style,
    }}
  >
    <img
      src="/logo-mark.png"
      alt="Organiflo"
      width={size}
      height={size}
      // Above the fold on every page it appears on: a logo that pops in late
      // is the first thing a visitor sees go wrong.
      loading="eager"
      // Lowercase: React 18 passes this straight through to the DOM and warns
      // on the camelCase spelling, which put an error in every console.
      fetchpriority="high"
      style={{
        width: size,
        height: size,
        display: 'block',
        flexShrink: 0,
        objectFit: 'contain',
      }}
    />

    {showWordmark && (
      <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.04 }}>
        <span
          className="logo-wordmark"
          style={{
            fontFamily: "'Bricolage Grotesque', system-ui, sans-serif",
            fontWeight: 800,
            fontSize: size * 0.58,
            letterSpacing: '-.03em',
            background: 'linear-gradient(100deg, #22d3ee, #3b82f6 46%, #8b5cf6)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            whiteSpace: 'nowrap',
          }}
        >
          Organiflo
        </span>
        {tagline && !noTagline && size >= TAGLINE_MIN_SIZE && (
          <span
            className="logo-tagline"
            style={{
              fontSize: Math.max(size * 0.26, 11),
              letterSpacing: '.005em',
              color: 'var(--text-muted)',
              fontWeight: 600,
              whiteSpace: 'nowrap',
            }}
          >
            Your Organic Social Growth Engine
          </span>
        )}
      </span>
    )}
  </span>
);

export default Logo;
