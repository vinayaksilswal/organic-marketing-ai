import React, { useState } from 'react';
import { ArrowRight, Check, X as XIcon, Loader2 } from 'lucide-react';
import { API_BASE, apiError} from '../config';

const PUBLIC_API = API_BASE.replace('/api/v1', '');

/**
 * The free audit: paste a URL, get a week of posts, no account.
 *
 * The page's other call to action asks a stranger to sign up before the
 * product has done anything for them. This asks for a URL and gives back
 * something they can act on today — the ask afterwards is "publish this",
 * which is a different question from "trust us".
 *
 * The score is a count of things actually found on their page, and every
 * check is shown, passed or failed, so they can look and disagree. It is
 * deliberately not a percentage: a number out of 100 reads as a measurement,
 * and we have no access to their accounts to measure anything.
 */
export default function GrowthAudit() {
  const [url, setUrl] = useState('');
  const [state, setState] = useState('idle');   // idle | loading | done | error
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState('');

  const run = async (e) => {
    e.preventDefault();
    if (!url.trim() || state === 'loading') return;

    setState('loading');
    setError('');
    try {
      const res = await fetch(`${PUBLIC_API}/api/public/growth-audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ websiteUrl: url.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // The server's own message is better than anything generic invented
        // here: it distinguishes "we could not read that page" from "you have
        // had your free runs".
        setError(apiError(body, 'Could not audit that site. Try the full address.'));
        setState('error');
        return;
      }
      setAudit(body);
      setState('done');
    } catch {
      setError('Could not reach us just now. Try again in a moment.');
      setState('error');
    }
  };

  const passed = (audit?.findings || []).filter((f) => f.passed);
  const missing = (audit?.findings || []).filter((f) => !f.passed);

  return (
    <div style={{ maxWidth: 780, margin: '0 auto' }}>
      <form
        onSubmit={run}
        style={{ display: 'flex', gap: '.6rem', flexWrap: 'wrap', justifyContent: 'center' }}
      >
        <input
          type="text"
          inputMode="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="yourbusiness.com"
          aria-label="Your website address"
          style={{
            flex: '1 1 300px',
            minHeight: 52,
            padding: '.85rem 1.1rem',
            borderRadius: 12,
            border: '1px solid var(--line)',
            background: '#fff',
            color: 'var(--ink)',
            fontSize: '1rem',
          }}
        />
        <button
          type="submit"
          className="b b-primary"
          disabled={state === 'loading'}
          style={{
            // height, not minHeight: the class supplies its own vertical
            // padding, which made the button 86px against a 52px input.
            height: 52,
            padding: '0 1.5rem',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '.5rem',
            whiteSpace: 'nowrap',
          }}
        >
          {state === 'loading' ? (
            <>
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              Reading your site…
            </>
          ) : (
            <>Get my free plan <ArrowRight size={16} /></>
          )}
        </button>
      </form>

      <p style={{ fontSize: '.82rem', color: 'var(--ink-faint)', textAlign: 'center', margin: '.7rem 0 0' }}>
        No account, no card. We read the page you give us and nothing else.
      </p>

      {state === 'error' && (
        <p style={{
          marginTop: '1.2rem', textAlign: 'center', fontSize: '.9rem',
          color: 'var(--ink-soft)', background: 'rgba(219,39,119,0.06)',
          border: '1px solid rgba(219,39,119,0.2)', borderRadius: 10, padding: '.85rem 1rem',
        }}>
          {error}
        </p>
      )}

      {state === 'done' && audit && (
        <div className="glass" style={{ marginTop: '1.8rem', padding: '1.75rem', textAlign: 'left' }}>
          <div style={{ borderBottom: '1px solid var(--line)', paddingBottom: '1.1rem', marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '.72rem', fontWeight: 800, letterSpacing: '.06em', color: 'var(--ink-faint)', textTransform: 'uppercase' }}>
              {audit.domain}
            </div>
            {audit.whatTheySell && (
              <p style={{ fontSize: '1.02rem', fontWeight: 600, margin: '.5rem 0 0', lineHeight: 1.5 }}>
                {audit.whatTheySell}
              </p>
            )}
            {audit.whoItIsFor && (
              <p style={{ fontSize: '.88rem', color: 'var(--ink-soft)', margin: '.35rem 0 0' }}>
                For {audit.whoItIsFor}
              </p>
            )}
          </div>

          {/* The count, said plainly. Never "72/100" -- that would be a
              measurement we did not make. */}
          <p style={{ fontSize: '.95rem', fontWeight: 700, margin: '0 0 .9rem' }}>
            {audit.scoreBasis}
          </p>

          <div style={{ display: 'grid', gap: '.5rem', marginBottom: '1.5rem' }}>
            {[...missing, ...passed].map((f) => (
              <div key={f.key} style={{ display: 'flex', gap: '.65rem', alignItems: 'flex-start' }}>
                {f.passed
                  ? <Check size={16} style={{ color: 'var(--green)', flexShrink: 0, marginTop: 3 }} />
                  : <XIcon size={16} style={{ color: 'var(--pink)', flexShrink: 0, marginTop: 3 }} />}
                <div>
                  <div style={{ fontSize: '.88rem', fontWeight: f.passed ? 500 : 700 }}>{f.label}</div>
                  {!f.passed && (
                    <div style={{ fontSize: '.82rem', color: 'var(--ink-soft)', lineHeight: 1.5 }}>{f.why}</div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <h3 style={{ fontSize: '1rem', fontWeight: 800, margin: '0 0 .8rem' }}>
            Your week, written for {audit.domain}
          </h3>
          <div style={{ display: 'grid', gap: '.45rem', marginBottom: '1.5rem' }}>
            {(audit.week || []).map((d) => (
              <div
                key={d.day}
                style={{
                  display: 'flex', gap: '.75rem', alignItems: 'baseline',
                  padding: '.6rem .8rem', borderRadius: 9,
                  background: 'rgba(11,16,32,0.025)',
                }}
              >
                <span style={{ fontSize: '.76rem', fontWeight: 800, minWidth: 74, color: 'var(--violet)' }}>
                  {d.day}
                </span>
                <span style={{ fontSize: '.7rem', fontWeight: 700, color: 'var(--ink-faint)', minWidth: 62 }}>
                  {d.format}
                </span>
                <span style={{ fontSize: '.87rem', lineHeight: 1.5 }}>{d.idea}</span>
              </div>
            ))}
          </div>

          <a href="/auth" className="b b-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '.5rem', textDecoration: 'none' }}>
            Publish this week automatically <ArrowRight size={16} />
          </a>
          <p style={{ fontSize: '.8rem', color: 'var(--ink-faint)', margin: '.7rem 0 0' }}>
            Free plan. Organiflo writes each post, attaches your video, and publishes on your schedule.
          </p>
        </div>
      )}
    </div>
  );
}
