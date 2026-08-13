import React, { useEffect, useRef, useState } from 'react';

/**
 * A number that counts up the first time it is scrolled into view.
 *
 * A live total is the strongest single number on the page -- it is the one
 * claim that is checkable and that grows on its own. Set at body-copy size it
 * read as a footnote; set large and animated it reads as momentum.
 *
 * Counts once, on entry, never again: a number that re-runs every time it
 * scrolls past stops being information and becomes decoration.
 *
 * Falls back to the final value immediately when IntersectionObserver is
 * unavailable or the viewer has asked for reduced motion, so the number is
 * always readable even if it never animates.
 */
const CountUp = ({ value, duration = 1500, style }) => {
  const [shown, setShown] = useState(0);
  const ref = useRef(null);
  const done = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || !value) return undefined;

    const stillness =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (stillness || typeof IntersectionObserver === 'undefined') {
      setShown(value);
      return undefined;
    }

    const run = () => {
      if (done.current) return;
      done.current = true;
      const start = performance.now();
      const tick = (now) => {
        const progress = Math.min((now - start) / duration, 1);
        // Eases out, so it decelerates into the final number rather than
        // stopping dead on it.
        const eased = 1 - Math.pow(1 - progress, 3);
        setShown(Math.round(value * eased));
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            run();
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );
    observer.observe(el);

    // If the observer never delivers — some embedded browsers do not
    // composite, and a stat that renders 0 forever is worse than one that
    // never animates — show the real number anyway.
    const failsafe = setTimeout(() => {
      if (!done.current) setShown(value);
    }, 1200);

    return () => {
      observer.disconnect();
      clearTimeout(failsafe);
    };
  }, [value, duration]);

  return <span ref={ref} style={style}>{shown.toLocaleString()}</span>;
};

export default CountUp;
