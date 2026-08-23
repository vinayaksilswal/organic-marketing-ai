import React, { useState } from 'react';
import { Sparkles, Copy, Check, RefreshCw, Target } from 'lucide-react';
import { API_BASE, authFetch, apiError } from '../config';

/**
 * Instagram creatives, built in stages rather than asked for in one breath.
 *
 * The progress list below is not decoration. Generating five creatives takes
 * a while, and a spinner with no account of itself reads as a hang — people
 * reload, which costs them a second run against their plan. Naming the stage
 * makes the wait legible.
 *
 * What is deliberately NOT shown: the angle scores, the rejected candidates,
 * the model's reasoning. The customer sees which angle was chosen and the
 * finished creative. A score on an unpublished creative would read as a
 * prediction of how it will perform, and this product does not make those.
 */

const STAGES = [
  'Reading your business',
  'Finding the angles that fit it',
  'Ranking them',
  'Writing the scenes',
  'Checking the format',
];

export default function StrategistCampaign({ token, activeWorkspaceId, showToast }) {
  const [count, setCount] = useState(3);
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState(-1);
  const [creatives, setCreatives] = useState([]);
  const [copied, setCopied] = useState('');

  const run = async () => {
    setRunning(true);
    setCreatives([]);
    setStage(0);

    // Advances on a timer because the server returns once, at the end. It is
    // an honest depiction of the order of work, not a fake progress bar
    // pretending to measure it — it stops at the last stage and waits.
    const tick = setInterval(
      () => setStage((s) => (s < STAGES.length - 1 ? s + 1 : s)),
      3500,
    );

    try {
      const res = await authFetch(`${API_BASE}/creatives/strategist-campaign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({ count: Number(count) }),
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiError(body, 'Could not build the campaign.'));
      setCreatives(body.creatives || []);
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      clearInterval(tick);
      setStage(-1);
      setRunning(false);
    }
  };

  const copy = (text, key) => {
    navigator.clipboard?.writeText(text || '');
    setCopied(key);
    setTimeout(() => setCopied(''), 1600);
  };

  return (
    <div style={{
      padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 14,
      border: '1px solid var(--border-color)', marginBottom: '2rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
        <Target size={18} color="var(--primary-color)" />
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Campaign builder</h2>
      </div>
      <p style={{ margin: '0 0 1.1rem', fontSize: '0.86rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
        Several creatives at once, each attacking a different reason somebody stops
        scrolling — pain, curiosity, transformation, demonstration, FOMO — rather than
        five rewordings of the same idea.
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <label style={{
            fontSize: '0.74rem', fontWeight: 800, color: 'var(--text-muted)',
            textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem',
          }}>
            How many
          </label>
          <div style={{ display: 'flex', gap: '0.35rem' }}>
            {[1, 3, 5].map((n) => (
              <button
                key={n}
                onClick={() => setCount(n)}
                style={{
                  minWidth: 52, minHeight: 44, borderRadius: 10, cursor: 'pointer',
                  fontWeight: 700, fontSize: '0.85rem',
                  background: count === n ? 'var(--primary-color)' : 'rgba(11,16,32,0.04)',
                  color: count === n ? '#fff' : 'var(--text-main)',
                  border: `1px solid ${count === n ? 'var(--primary-color)' : 'var(--border-color)'}`,
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={run}
          disabled={running}
          className="btn btn-primary"
          style={{ minHeight: 44, display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}
        >
          {running ? <RefreshCw size={16} className="spin" /> : <Sparkles size={16} />}
          {running ? 'Building…' : 'Build the campaign'}
        </button>
      </div>

      {running && (
        <div style={{ marginTop: '1.25rem', display: 'grid', gap: '0.4rem' }}>
          {STAGES.map((label, i) => (
            <div
              key={label}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.84rem',
                color: i <= stage ? 'var(--text-main)' : 'var(--text-muted)',
                opacity: i <= stage ? 1 : 0.5,
              }}
            >
              {i < stage
                ? <Check size={14} style={{ color: 'var(--success)' }} />
                : <span style={{
                    width: 14, height: 14, borderRadius: '50%',
                    border: `2px solid ${i === stage ? 'var(--primary-color)' : 'var(--border-color)'}`,
                  }} />}
              {label}
            </div>
          ))}
        </div>
      )}

      {creatives.length > 0 && (
        <div style={{ marginTop: '1.75rem', display: 'grid', gap: '1.25rem' }}>
          {creatives.map((c, i) => (
            <div
              key={i}
              style={{
                border: '1px solid var(--border-color)', borderRadius: 12,
                background: 'rgba(11,16,32,0.02)', padding: '1.25rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-muted)' }}>
                  CREATIVE {String(i + 1).padStart(2, '0')}
                </span>
                {/* The chosen angle, not the score. A number on an
                    unpublished creative reads as a forecast. */}
                <span style={{
                  fontSize: '0.7rem', fontWeight: 800, padding: '0.12rem 0.5rem',
                  borderRadius: 999, background: 'rgba(109,40,217,0.10)', color: 'var(--primary-color)',
                  textTransform: 'capitalize',
                }}>
                  {(c.creative_angle || 'general').replace(/_/g, ' ')}
                </span>
                {c.selling_angle && (
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Sells: {c.selling_angle}
                  </span>
                )}
                <button
                  onClick={() => copy(c.markdown, `c${i}`)}
                  className="btn btn-secondary"
                  style={{ marginLeft: 'auto', minHeight: 34, fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                >
                  {copied === `c${i}` ? <Check size={13} /> : <Copy size={13} />}
                  {copied === `c${i}` ? 'Copied' : 'Copy'}
                </button>
              </div>

              <pre style={{
                margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                fontSize: '0.79rem', lineHeight: 1.65, color: 'var(--text-main)',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                background: 'rgba(11,16,32,0.03)', borderRadius: 10, padding: '1rem',
                maxHeight: 420, overflowY: 'auto',
              }}>{c.markdown}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
