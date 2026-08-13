import React from 'react';

/**
 * The Organiflo mark: a cloud with a leaf through it, teal into violet.
 *
 * Inline SVG rather than the PNG. It stays crisp at every size from a 16px
 * favicon to a hero, needs no network request on the page that has to load
 * fastest, and its gradient is defined in CSS terms so it can be recoloured
 * per surface instead of shipping a second file for the dark sidebar.
 *
 * Each instance mints its own gradient id. Two logos on one page sharing an
 * id means the second one silently references the first one's definition, and
 * if the first unmounts the second loses its fill entirely -- a bug that only
 * shows up once the mark appears twice, which is exactly when nobody is
 * looking for it.
 */
const Logo = ({ size = 30, showWordmark = false, tagline = false, style }) => {
  const uid = React.useId();
  const gradient = `organiflo-g-${uid}`;
  const glow = `organiflo-glow-${uid}`;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '.6rem', ...style }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        role="img"
        aria-label="Organiflo"
        style={{ flexShrink: 0, display: 'block' }}
      >
        <defs>
          <linearGradient id={gradient} x1="6" y1="46" x2="58" y2="16" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#7c3aed" />
            <stop offset="45%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#22d3ee" />
          </linearGradient>
          <filter id={glow} x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="1.6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g filter={`url(#${glow})`}>
          {/* The cloud, drawn as an outline so the leaf can pass through it */}
          <path
            d="M20 45.5h24a10.5 10.5 0 0 0 .6-21 14 14 0 0 0-26.2-3.1A9.8 9.8 0 0 0 20 45.5Z"
            stroke={`url(#${gradient})`}
            strokeWidth="3.2"
            strokeLinejoin="round"
            fill="none"
          />
          {/* The leaf, cutting across the cloud on the diagonal */}
          <path
            d="M24 42c-2.5-9 3-17.5 15.5-19.5C38 32 33 40 24 42Z"
            fill={`url(#${gradient})`}
          />
          {/* Its midrib, the detail that makes it read as a leaf at 16px */}
          <path
            d="M24.6 41.6C28.5 34.8 33 28.8 39.2 22.8"
            stroke="#0b1020"
            strokeOpacity=".35"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </g>
      </svg>

      {showWordmark && (
        <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
          <span
            style={{
              fontFamily: "'Bricolage Grotesque', system-ui, sans-serif",
              fontWeight: 800,
              fontSize: size * 0.62,
              letterSpacing: '-.028em',
              background: 'linear-gradient(100deg, #22d3ee, #3b82f6 48%, #a855f7)',
              WebkitBackgroundClip: 'text',
              backgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Organiflo
          </span>
          {tagline && (
            <span style={{
              fontSize: size * 0.235,
              letterSpacing: '.02em',
              color: 'currentColor',
              opacity: .62,
              fontWeight: 500,
            }}>
              Your Organic Social Growth Engine
            </span>
          )}
        </span>
      )}
    </span>
  );
};

export default Logo;
