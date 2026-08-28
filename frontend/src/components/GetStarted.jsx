import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ArrowRight, Circle } from 'lucide-react';

/**
 * The path from a new account to a first published post.
 *
 * WHY AN ORDERED LIST AND NOT A LIST OF PROBLEMS
 * ----------------------------------------------
 * The dashboard already showed blockers — an unordered set of things that
 * were wrong. That is useful to somebody who already understands the product
 * and useless to somebody who signed up ten minutes ago, because it does not
 * say what to do FIRST. Five problems presented at once read as five reasons
 * to close the tab.
 *
 * This is the same information as a sequence, with exactly one thing lit up
 * at a time: the next step. Everything after it is dimmed, everything before
 * it is ticked.
 *
 * WHERE THE PLAN SITS
 * -------------------
 * Fourth, after the business is set up and an account is connected, and
 * before the first post. Asking for money on step one, before anybody has
 * seen the product do anything, is how a free signup becomes a closed tab.
 * Asking after the first post means giving the whole product away and hoping.
 * Between the setup and the payoff is where somebody can see what they would
 * be buying and has not yet had it for free.
 *
 * It disappears entirely once every step is done. A permanent checklist on a
 * working account is clutter that trains people to ignore the top of the page.
 */
export default function GetStarted({
  hasBusiness, hasAccount, hasMedia, hasPlan, hasPosted, onPostNow, posting,
}) {
  const navigate = useNavigate();

  const steps = [
    {
      done: !!hasBusiness,
      title: 'Add your business',
      why: 'What you sell, who buys it, how you sound. Everything written here comes from this.',
      cta: 'Set up business',
      go: () => navigate('/dashboard/workspaces'),
    },
    {
      done: !!hasAccount,
      title: 'Connect a social account',
      why: 'Facebook, Instagram, X, LinkedIn or YouTube. One is enough to start.',
      cta: 'Connect an account',
      go: () => navigate('/dashboard/workspaces'),
    },
    {
      done: !!hasMedia,
      title: 'Add something to post',
      why: 'Upload photos, or generate them. Instagram will not publish without an image or video.',
      cta: 'Open media library',
      go: () => navigate('/dashboard/media-catalog'),
    },
    {
      done: !!hasPlan,
      title: 'Choose your plan',
      why: 'Posting runs on its own from here. Pick the plan that matches how often you want to show up.',
      cta: 'See plans',
      go: () => navigate('/dashboard/billing'),
    },
    {
      done: !!hasPosted,
      title: 'Publish your first post',
      why: 'Runs one cycle now instead of waiting for the next scheduled one.',
      cta: posting ? 'Starting…' : 'Post now',
      go: onPostNow,
      disabled: posting || !onPostNow,
    },
  ];

  const doneCount = steps.filter((s) => s.done).length;
  if (doneCount === steps.length) return null;

  // The first unfinished step. Only this one gets a button.
  const nextIndex = steps.findIndex((s) => !s.done);

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border-color)',
      borderRadius: 14, padding: '1.4rem', marginBottom: '1.5rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '0.3rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Get your first post out</h2>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>
          {doneCount} of {steps.length} done
        </span>
      </div>
      <p style={{ margin: '0 0 1.1rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
        Five steps, once. After that it posts on its own.
      </p>

      {/* A real bar rather than a count: progress you can see at a glance is
          what makes somebody finish step four. */}
      <div style={{
        height: 5, borderRadius: 999, background: 'rgba(11,16,32,0.07)',
        overflow: 'hidden', marginBottom: '1.2rem',
      }}>
        <div style={{
          width: `${(doneCount / steps.length) * 100}%`, height: '100%',
          background: 'linear-gradient(90deg, var(--primary-color), var(--secondary-color))',
          transition: 'width 300ms ease',
        }} />
      </div>

      <div style={{ display: 'grid', gap: '0.15rem' }}>
        {steps.map((step, i) => {
          const isNext = i === nextIndex;
          return (
            <div
              key={step.title}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: '0.7rem',
                padding: '0.7rem 0.75rem', borderRadius: 10,
                background: isNext ? 'rgba(139,92,246,0.06)' : 'transparent',
                border: `1px solid ${isNext ? 'rgba(139,92,246,0.22)' : 'transparent'}`,
                // Steps after the current one are dimmed: they are not the
                // decision in front of you yet.
                opacity: step.done || isNext ? 1 : 0.45,
              }}
            >
              <div style={{ marginTop: 2, flexShrink: 0 }}>
                {step.done
                  ? <Check size={16} style={{ color: 'var(--success)' }} />
                  : <Circle size={16} style={{ color: isNext ? 'var(--primary-color)' : 'var(--text-muted)' }} />}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: '0.88rem', fontWeight: 700,
                  textDecoration: step.done ? 'line-through' : 'none',
                  color: step.done ? 'var(--text-muted)' : 'var(--text-main)',
                }}>
                  {step.title}
                </div>
                {isNext && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5, marginTop: '0.15rem' }}>
                    {step.why}
                  </div>
                )}
              </div>

              {isNext && (
                <button
                  onClick={step.go}
                  disabled={step.disabled}
                  className="btn btn-primary"
                  style={{
                    flexShrink: 0, minHeight: 38, fontSize: '0.8rem', fontWeight: 700,
                    display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                  }}
                >
                  {step.cta} <ArrowRight size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
