import React, { useEffect, useState } from 'react';
import { Monitor, X } from 'lucide-react';

/**
 * A one-line note, on phones only, that the dashboard has more room on a
 * desktop.
 *
 * Deliberately a bar and not a modal. Everything here works on a phone — the
 * hint is that some of it is *easier* with the width, which is advice, and
 * advice that blocks the screen it is describing reads as a wall. It appears
 * once, remembers being dismissed, and never argues.
 *
 * Shown below the top bar rather than pinned to the bottom so it scrolls away
 * with the page instead of permanently eating 40px of a small screen.
 */
const STORAGE_KEY = 'organiflo:desktop-hint-dismissed';
const BREAKPOINT = 900;

const DesktopHint = () => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === '1') return undefined;

    const check = () => setShow(window.innerWidth <= BREAKPOINT);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  if (!show) return null;

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, '1');
    setShow(false);
  };

  // Carries its own container so the layout does not reserve padding for a
  // bar that renders nothing on desktop or after dismissal.
  return (
    <div className="container" style={{ paddingTop: '1rem' }}>
    <div
      role="status"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.6rem',
        padding: '0.7rem 0.8rem',
        borderRadius: 10,
        background: 'rgba(109, 40, 217, 0.06)',
        border: '1px solid rgba(109, 40, 217, 0.18)',
        color: 'var(--text-main)',
        fontSize: '0.84rem',
        lineHeight: 1.45,
      }}
    >
      <Monitor size={17} color="var(--primary-color)" style={{ flexShrink: 0 }} />
      <span style={{ flex: 1, minWidth: 0 }}>
        Everything here works on your phone. For the calendar, bulk uploads and
        the video studio, a desktop gives you a lot more room.
      </span>
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        style={{
          flexShrink: 0,
          width: 32, height: 32, borderRadius: 8,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          background: 'transparent', border: 'none', cursor: 'pointer',
          color: 'var(--text-muted)',
        }}
      >
        <X size={15} />
      </button>
    </div>
    </div>
  );
};

export default DesktopHint;
