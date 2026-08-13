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
const Logo = ({ size = 30, showWordmark = false, noTagline = false, style }) => {
  // Three cuts of the same artwork, each for the size it is used at:
  //   logo.png         mark + wordmark + tagline, for heroes and share cards
  //   logo-lockup.png  mark + wordmark, for navigation
  //   logo-mark.png    the mark alone, squared, for avatars and the favicon
  //
  // The tagline is dropped from the nav cut deliberately. In a 34px bar it
  // renders around six pixels tall, which is not small type — it is grey
  // mush that makes the whole lockup look blurred.
  // The full lockup, tagline included, is the default wherever the wordmark
  // shows. Cutting the tagline off left a ghost of its glow under the word --
  // neon type carries a halo above its own letterforms, so no horizontal cut
  // separates the two lines cleanly. It also threw away the line that says
  // what the company does, on the one surface every visitor sees.
  //
  // The size is what makes it legible: at 34px tall the tagline is six pixels
  // of mush, so the nav uses 46 and the strapline reads.
  const src = showWordmark
    ? (noTagline ? '/logo-lockup.png' : '/logo.png')
    : '/logo-mark.png';

  // The lockups are wide, so height is the dimension worth fixing; width
  // follows. The mark is square.
  const dimensions = showWordmark
    ? { height: size, width: 'auto' }
    : { height: size, width: size };

  return (
    <img
      src={src}
      alt="Organiflo"
      // Eager and high priority: this sits above the fold on every page it
      // appears on, and a logo that pops in late is the first thing a visitor
      // sees go wrong.
      loading="eager"
      fetchPriority="high"
      style={{
        ...dimensions,
        display: 'block',
        flexShrink: 0,
        objectFit: 'contain',
        ...style,
      }}
    />
  );
};

export default Logo;
