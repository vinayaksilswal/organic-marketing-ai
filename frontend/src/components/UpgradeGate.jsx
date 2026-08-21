import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, X } from 'lucide-react';

/**
 * The upgrade prompt, shown whenever the server refuses a request on plan
 * limits.
 *
 * Every quota check in the backend answers 402 with a sentence written for the
 * person who hit it — "You have used all 5 published posts included in the
 * Free plan this month." Until now those sentences arrived as a red toast
 * indistinguishable from a network failure, at the one moment a free account
 * is most willing to pay. This turns that moment into the ask.
 *
 * Mounted once, listening on the window, so no page has to know it exists and
 * every future endpoint that returns 402 gets it for free.
 */
const UpgradeGate = () => {
  const navigate = useNavigate();
  const [message, setMessage] = useState(null);

  useEffect(() => {
    const onLimit = (e) => setMessage(e.detail?.message || '');
    window.addEventListener('organiflo:upgrade-required', onLimit);
    return () => window.removeEventListener('organiflo:upgrade-required', onLimit);
  }, []);

  // Escape closes it. A modal you cannot dismiss with the keyboard reads as a
  // fault rather than an offer.
  useEffect(() => {
    if (message === null) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setMessage(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [message]);

  if (message === null) return null;

  const close = () => setMessage(null);

  return (
    <div
      onClick={close}
      style={{
        position: 'fixed', inset: 0, zIndex: 4000,
        background: 'rgba(11, 16, 32, 0.45)',
        backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '1.25rem',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="upgrade-gate-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--bg-card-hover)',
          border: '1px solid var(--border-color)',
          borderRadius: 16,
          boxShadow: 'var(--shadow-xl)',
          padding: '2rem',
          width: '100%',
          maxWidth: 440,
          position: 'relative',
        }}
      >
        <button
          onClick={close}
          aria-label="Close"
          style={{
            position: 'absolute', top: 8, right: 8,
            // 40px rather than the icon's size: a dismissal people miss on a
            // phone reads as a modal that will not close.
            width: 40, height: 40, borderRadius: 10,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)',
          }}
        >
          <X size={18} />
        </button>

        <div style={{
          width: 44, height: 44, borderRadius: 10,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(109, 40, 217, 0.10)',
          color: 'var(--primary-color)',
          marginBottom: '1rem',
        }}>
          <Sparkles size={22} />
        </div>

        <h3
          id="upgrade-gate-title"
          style={{
            margin: '0 0 0.6rem',
            fontFamily: 'var(--font-family-heading)',
            fontSize: '1.35rem',
            color: 'var(--text-main)',
          }}
        >
          You have outgrown the free plan
        </h3>

        {/* The server's own sentence, because it names the exact limit that was
            hit. The fallback only runs if the response body was unreadable. */}
        <p style={{
          margin: '0 0 1.5rem',
          color: 'var(--text-muted)',
          fontSize: '0.95rem',
          lineHeight: 1.6,
        }}>
          {message || 'This action needs a paid plan. Upgrade to keep going.'}
        </p>

        <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
          <button
            className="btn-primary"
            onClick={() => { close(); navigate('/dashboard/billing'); }}
            style={{ flex: '1 1 200px', minHeight: 44 }}
          >
            See plans
          </button>
          <button
            onClick={close}
            style={{
              flex: '0 1 auto', minHeight: 44, padding: '0 1.1rem',
              borderRadius: 10, cursor: 'pointer',
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-family-body)',
              fontWeight: 600,
            }}
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  );
};

export default UpgradeGate;
