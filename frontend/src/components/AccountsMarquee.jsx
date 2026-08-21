import React, { useEffect, useState } from 'react';
import { Instagram, Facebook } from 'lucide-react';

import { API_BASE } from '../config';

const PUBLIC_API = API_BASE.replace('/api/v1', '');

/**
 * A continuously scrolling strip of the real accounts publishing through the
 * platform.
 *
 * Stronger than a logo wall because every chip is clickable: a visitor can
 * open one and see posts arriving on a schedule, which is the actual claim
 * the page is making. It also grows on its own as customers connect accounts.
 *
 * The scroll is one CSS animation over a doubled list rather than a timer.
 * The second copy makes the wrap seamless -- when the track has moved exactly
 * one copy's width, the frame is identical to the start, so resetting is
 * invisible. Nothing runs in JavaScript, so it costs nothing on the page that
 * has to load fastest.
 *
 * Renders nothing at all when no accounts come back. An empty proof strip is
 * worse than no strip.
 */
const css = `
@keyframes omai-marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.omai-marquee-mask {
  position: relative; overflow: hidden; width: 100%;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 7%, #000 93%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 7%, #000 93%, transparent);
}
.omai-marquee-track {
  display: flex; gap: .85rem; width: max-content;
  animation: omai-marquee 46s linear infinite;
}
.omai-marquee-mask:hover .omai-marquee-track { animation-play-state: paused; }
.omai-chip {
  display: inline-flex; align-items: center; gap: .68rem;
  padding: .55rem .95rem .55rem .58rem;
  border-radius: 999px; text-decoration: none; white-space: nowrap;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(11,16,32,0.09);
  box-shadow: 0 1px 2px rgba(11,16,32,0.04), 0 10px 24px -14px rgba(11,16,32,0.22);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
  transition: transform .2s cubic-bezier(.4,0,.2,1), box-shadow .2s, border-color .2s;
}
.omai-chip:hover {
  transform: translateY(-2px);
  border-color: rgba(139,92,246,0.34);
  box-shadow: 0 1px 2px rgba(11,16,32,0.04), 0 16px 32px -14px rgba(109,40,217,0.4);
}
.omai-chip-av {
  width: 34px; height: 34px; border-radius: 999px; object-fit: cover; flex-shrink: 0;
  background: linear-gradient(135deg, #6d28d9, var(--secondary-color));
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: .84rem;
}
@media (prefers-reduced-motion: reduce) {
  .omai-marquee-track { animation: none; flex-wrap: wrap; justify-content: center; width: 100%; }
}
`;

const Chip = ({ account }) => {
  const [broken, setBroken] = useState(false);
  const Icon = account.platform === 'instagram' ? Instagram : Facebook;
  const tint = account.platform === 'instagram' ? '#db2777' : 'var(--secondary-color)';

  return (
    <a
      className="omai-chip"
      href={account.url}
      target="_blank"
      rel="noopener noreferrer"
      title={`Open ${account.name} on ${account.platform === 'instagram' ? 'Instagram' : 'Facebook'}`}
    >
      {account.avatar && !broken ? (
        <img
          className="omai-chip-av"
          src={account.avatar}
          alt=""
          loading="lazy"
          onError={() => setBroken(true)}
        />
      ) : (
        // Two of the live accounts return no profile picture, so the initial
        // stands in rather than leaving a broken-image box on the page.
        <span className="omai-chip-av">{(account.name || '?').charAt(0).toUpperCase()}</span>
      )}
      <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.28 }}>
        {/* The account name is the whole point of the strip -- it is the
            evidence. It was set smaller than the platform label it sits
            above, which buried it. */}
        <span style={{ fontSize: '.98rem', fontWeight: 700, color: '#0b1020', letterSpacing: '-.012em' }}>
          {account.name}
        </span>
        <span style={{ fontSize: '.72rem', color: tint, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '.3rem' }}>
          <Icon size={12} color={tint} />
          {account.platform === 'instagram' ? 'Instagram' : 'Facebook Page'}
        </span>
      </span>
    </a>
  );
};

const AccountsMarquee = () => {
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    let alive = true;
    fetch(`${PUBLIC_API}/api/public/connected-accounts`)
      .then((r) => (r.ok ? r.json() : { accounts: [] }))
      .then((data) => { if (alive) setAccounts(data.accounts || []); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  if (!accounts.length) return null;

  // Doubled so the animation can travel exactly one copy and wrap invisibly.
  const track = [...accounts, ...accounts];

  return (
    <div style={{ padding: '0 0 1rem' }}>
      <style>{css}</style>
      {/* No count. A number invites the reader to judge how small it is, and
          it would have to be maintained as truth as the list changes. The
          accounts themselves are the claim. */}
      <p style={{
        textAlign: 'center', fontSize: '.74rem', fontWeight: 700,
        letterSpacing: '.1em', textTransform: 'uppercase',
        color: '#94a3b8', marginBottom: '1.15rem',
      }}>
        Publishing on autopilot right now
      </p>
      <div className="omai-marquee-mask">
        <div className="omai-marquee-track">
          {track.map((account, i) => (
            <Chip key={`${account.platform}-${account.name}-${i}`} account={account} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default AccountsMarquee;
