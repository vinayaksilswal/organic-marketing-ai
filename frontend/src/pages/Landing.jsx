import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2, Sparkles, ArrowRight, ChevronDown, ShieldCheck,
  Instagram, Facebook, Wand2, Clock, Eye, Send, AlertCircle,
} from 'lucide-react';
import { Helmet } from 'react-helmet-async';

import { API_BASE } from '../config';
const PUBLIC_API = API_BASE.replace('/api/v1', '');

/*
  The app shell is dark and the dashboard depends on those CSS variables, so
  every style here is scoped under .omai — the landing page renders light
  without touching the rest of the product.

  Translucency is done with real backdrop-filter over coloured washes rather
  than flat grey fills, which is what stops a white page looking like a
  document.
*/
const styles = `
.omai {
  --ink:        #0b1020;
  --ink-soft:   #475569;
  --ink-faint:  #94a3b8;
  --violet:     #6d28d9;
  --violet-lit: #8b5cf6;
  --blue:       #2563eb;
  --pink:       #db2777;
  --green:      #059669;
  --line:       rgba(11,16,32,0.09);
  --glass:      rgba(255,255,255,0.72);
  --glass-hi:   rgba(255,255,255,0.9);

  background: #fff;
  color: var(--ink);
  font-synthesis: none;
  -webkit-font-smoothing: antialiased;
  position: relative;
  overflow-x: hidden;
}
/* Colour washes. These sit behind everything and are what the frosted
   surfaces blur, so the page reads as light-with-colour, not grey. */
.omai::before {
  content: '';
  position: absolute; inset: 0 0 auto 0; height: 1400px;
  background:
    radial-gradient(900px 520px at 78% -6%,  rgba(139,92,246,0.20), transparent 62%),
    radial-gradient(760px 460px at 12% 6%,   rgba(37,99,235,0.16),  transparent 60%),
    radial-gradient(680px 420px at 55% 42%,  rgba(219,39,119,0.09), transparent 62%);
  pointer-events: none; z-index: 0;
}
.omai > * { position: relative; z-index: 1; }

.omai h1, .omai h2, .omai h3 { color: var(--ink); letter-spacing: -0.028em; margin: 0; }
.omai p { color: var(--ink-soft); margin: 0; }
.omai section { padding: 6rem 0; }
.omai .wrap { width: 100%; max-width: 1180px; margin: 0 auto; padding: 0 1.5rem; }

.omai .eyebrow {
  display: inline-flex; align-items: center; gap: .45rem;
  font-size: .74rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--violet); background: rgba(139,92,246,0.10);
  border: 1px solid rgba(139,92,246,0.22);
  padding: .4rem .8rem; border-radius: 999px;
}

/* Frosted surfaces */
.omai .glass {
  background: var(--glass);
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  border: 1px solid rgba(255,255,255,0.85);
  box-shadow: 0 1px 2px rgba(11,16,32,0.04), 0 12px 32px -12px rgba(11,16,32,0.14);
  border-radius: 18px;
}
.omai .glass-lift { transition: transform .25s cubic-bezier(.4,0,.2,1), box-shadow .25s; }
.omai .glass-lift:hover {
  transform: translateY(-4px);
  box-shadow: 0 1px 2px rgba(11,16,32,0.04), 0 26px 54px -18px rgba(109,40,217,0.30);
}

/* Translucent buttons */
.omai .b {
  display: inline-flex; align-items: center; justify-content: center; gap: .5rem;
  font-weight: 650; font-size: .95rem; border-radius: 12px; padding: .85rem 1.5rem;
  cursor: pointer; border: 1px solid transparent; text-decoration: none;
  transition: transform .18s, box-shadow .22s, background .22s;
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
}
.omai .b:active { transform: translateY(1px); }
.omai .b-primary {
  color: #fff;
  background: linear-gradient(135deg, rgba(109,40,217,0.94), rgba(37,99,235,0.94));
  border-color: rgba(255,255,255,0.24);
  box-shadow: 0 8px 24px -8px rgba(109,40,217,0.6), inset 0 1px 0 rgba(255,255,255,0.28);
}
.omai .b-primary:hover {
  box-shadow: 0 14px 34px -10px rgba(109,40,217,0.7), inset 0 1px 0 rgba(255,255,255,0.34);
  transform: translateY(-2px);
}
.omai .b-ghost {
  color: var(--ink); background: rgba(255,255,255,0.62);
  border-color: rgba(11,16,32,0.10);
  box-shadow: 0 1px 2px rgba(11,16,32,0.04);
}
.omai .b-ghost:hover { background: rgba(255,255,255,0.9); transform: translateY(-2px); }
.omai .b:disabled { opacity: .55; cursor: not-allowed; transform: none; }

.omai .nav {
  position: sticky; top: 0; z-index: 60;
  background: rgba(255,255,255,0.7);
  backdrop-filter: blur(16px) saturate(160%);
  -webkit-backdrop-filter: blur(16px) saturate(160%);
  border-bottom: 1px solid var(--line);
}
.omai .nav-in {
  max-width: 1180px; margin: 0 auto; padding: .8rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
}
.omai .brand { display: flex; align-items: center; gap: .55rem; font-weight: 750; font-size: 1.1rem; cursor: pointer; letter-spacing: -.02em; }

.omai .grid { display: grid; gap: 1.25rem; }
.omai .g2 { grid-template-columns: repeat(auto-fit, minmax(300px,1fr)); }
.omai .g3 { grid-template-columns: repeat(auto-fit, minmax(260px,1fr)); }
.omai .g4 { grid-template-columns: repeat(auto-fit, minmax(230px,1fr)); }

.omai .h1 { font-size: clamp(2.5rem, 5.4vw, 4rem); line-height: 1.04; font-weight: 780; }
.omai .h2 { font-size: clamp(1.9rem, 3.2vw, 2.6rem); line-height: 1.12; font-weight: 740; }
.omai .lede { font-size: clamp(1.02rem, 1.35vw, 1.18rem); line-height: 1.62; }
.omai .tint {
  background: linear-gradient(120deg, var(--violet), var(--blue) 55%, var(--pink));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}

.omai .faq { border-bottom: 1px solid var(--line); }
.omai .faq button {
  width: 100%; background: none; border: 0; padding: 1.35rem 0; cursor: pointer;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  font-size: 1.02rem; font-weight: 640; color: var(--ink); text-align: left;
}
.omai .faq .a { overflow: hidden; max-height: 0; transition: max-height .3s ease; }
.omai .faq .a.open { max-height: 420px; }

.omai .price-pop {
  position: absolute; top: -13px; left: 50%; transform: translateX(-50%);
  background: linear-gradient(135deg, var(--violet), var(--blue));
  color: #fff; padding: .25rem .8rem; border-radius: 999px;
  font-size: .66rem; font-weight: 800; letter-spacing: .07em; white-space: nowrap;
  box-shadow: 0 6px 18px -6px rgba(109,40,217,0.7);
}
.omai .field {
  width: 100%; padding: .85rem 1rem; border-radius: 12px;
  background: rgba(255,255,255,0.8); border: 1px solid rgba(11,16,32,0.12);
  color: var(--ink); font-size: .95rem; outline: none;
}
.omai .field:focus { border-color: var(--violet-lit); box-shadow: 0 0 0 3px rgba(139,92,246,0.16); }

@media (max-width: 720px) {
  .omai section { padding: 4rem 0; }
}
`;

const Landing = () => {
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState(null);
  const [stats, setStats] = useState(null);

  // Mirrors services/billing_service.PLANS. A pricing block that renders a
  // spinner when the API is unreachable sells nothing, so the page always has
  // prices to show and upgrades to live data when it arrives.
  const FALLBACK_PLANS = [
    { code: 'free', name: 'Free', price: 0, tagline: 'Run the whole thing before you pay.',
      features: ['1 business', '5 published posts a month', '3 AI creative briefs a month', 'Facebook + Instagram publishing'] },
    { code: 'starter', name: 'Starter', price: 17, tagline: 'One business, running itself.',
      features: ['1 business', '60 published posts a month', '30 AI creative briefs a month', '1,000 marketing emails a month', 'Publishes every 2 hours'] },
    { code: 'growth', name: 'Growth', price: 49, tagline: 'Several brands, one operator.',
      features: ['5 businesses', '300 published posts a month', '150 AI creative briefs a month', '10,000 marketing emails a month', 'Your own email sending domain'] },
    { code: 'agency', name: 'Agency', price: 149, tagline: 'Run marketing for clients.',
      features: ['25 businesses', 'Unlimited published posts', '600 AI creative briefs a month', '50,000 marketing emails a month', 'Team seats and roles'] },
  ];
  const [plans, setPlans] = useState(FALLBACK_PLANS);

  // Live demo
  const [bizName, setBizName] = useState('');
  const [bizModel, setBizModel] = useState('SaaS');
  const [bizDesc, setBizDesc] = useState('');
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoOut, setDemoOut] = useState(null);
  const [demoErr, setDemoErr] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/billing/plans`)
      .then(r => r.json())
      .then(d => { if (Array.isArray(d?.plans) && d.plans.length) setPlans(d.plans); })
      .catch(() => {});
    fetch(`${PUBLIC_API}/api/public/stats`)
      .then(r => r.json()).then(setStats).catch(() => {});
  }, []);

  const entry = Math.min(...plans.filter(p => p.price > 0).map(p => p.price), 17);

  const runDemo = async (e) => {
    e.preventDefault();
    if (!bizName.trim()) return;
    setDemoBusy(true); setDemoErr(null); setDemoOut(null);
    try {
      const res = await fetch(`${PUBLIC_API}/api/public/demo-caption`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ businessName: bizName, businessModel: bizModel, description: bizDesc }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        // 429 carries a message written for the visitor. Anything else is a
        // server string like "Not Found" that means nothing to them.
        throw new Error(
          res.status === 429
            ? (data.detail || 'You have used the free preview a few times. Create an account to keep going — it is free.')
            : 'The preview is not available right now. You can still start free and write your first post inside the app.'
        );
      }
      if (!data.caption) throw new Error('The AI returned nothing this time. Please try again.');
      setDemoOut(data.caption);
    } catch (err) {
      setDemoErr(err.message);
    } finally {
      setDemoBusy(false);
    }
  };

  const faqs = [
    ['Does anything post without my approval?',
     'No. Auto-approve is off by default. Every generated post waits in a review log where you can edit or delete it. Turn auto-approve on only when you are happy with what it writes.'],
    ['Which platforms does it publish to?',
     'Facebook Pages and Instagram, connected in one click through Meta — including Reels. X and LinkedIn can also publish, but you supply your own API token for those rather than clicking Connect.'],
    ['How does it learn my brand?',
     'It reads your website and builds a profile: what you sell, who buys it, your tone, your content themes. Every caption is written from that profile plus a description of the specific image or video attached, so posts reference what is actually on screen.'],
    ['What do I actually get for free?',
     'A real business workspace, brand analysis, five published posts and three AI creative briefs a month. No card. It is the same product, metered lower.'],
    ['Can I cancel?',
     'Any time, from your dashboard. Billing is monthly through PayPal and cancelling keeps your access until the end of the period you already paid for.'],
    ['Do you store my card details?',
     'No. Payment happens entirely inside PayPal. We never see or store card numbers.'],
  ];

  return (
    <div className="omai">
      <style>{styles}</style>
      <Helmet>
        <title>OrganicAI — Organic marketing that runs itself</title>
        <meta name="description" content="AI writes brand-matched social posts and publishes them to your Facebook Page and Instagram on a schedule you set. Free plan, no card required." />
        <script type="application/ld+json">{JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'SoftwareApplication',
          name: 'OrganicAI',
          applicationCategory: 'BusinessApplication',
          offers: { '@type': 'Offer', price: String(entry), priceCurrency: 'USD' },
          description: 'Automated organic marketing for small businesses',
        })}</script>
      </Helmet>

      {/* NAV */}
      <nav className="nav">
        <div className="nav-in">
          <div className="brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <Sparkles size={20} color="#6d28d9" /> OrganicAI
          </div>
          <div style={{ display: 'flex', gap: '.6rem', alignItems: 'center' }}>
            <button className="b b-ghost" style={{ padding: '.6rem 1rem' }} onClick={() => navigate('/auth')}>Log in</button>
            <button className="b b-primary" style={{ padding: '.6rem 1.15rem' }} onClick={() => navigate('/auth')}>Start free</button>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section style={{ paddingTop: '5rem', paddingBottom: '4rem' }}>
        <div className="wrap" style={{ textAlign: 'center' }}>
          <span className="eyebrow"><Sparkles size={13} /> Free plan · no card</span>

          <h1 className="h1" style={{ margin: '1.4rem auto 0', maxWidth: 940 }}>
            Your marketing runs<br />
            <span className="tint">while you run the business.</span>
          </h1>

          <p className="lede" style={{ maxWidth: 640, margin: '1.5rem auto 0' }}>
            Add your website once. OrganicAI learns what you sell, writes the copy and the
            creative brief, and publishes to your Facebook Page and Instagram on the schedule
            you set — with every post reviewable before it goes out.
          </p>

          <div style={{ display: 'flex', gap: '.8rem', justifyContent: 'center', marginTop: '2.2rem', flexWrap: 'wrap' }}>
            <button className="b b-primary" style={{ padding: '1rem 1.9rem', fontSize: '1rem' }} onClick={() => navigate('/auth')}>
              Start free <ArrowRight size={17} />
            </button>
            <button className="b b-ghost" style={{ padding: '1rem 1.6rem', fontSize: '1rem' }}
              onClick={() => document.getElementById('try')?.scrollIntoView({ behavior: 'smooth' })}>
              Watch it write one <Wand2 size={16} />
            </button>
          </div>

          <p style={{ fontSize: '.85rem', color: 'var(--ink-faint)', marginTop: '1.1rem' }}>
            Nothing publishes until you allow it · Cancel any time
          </p>

          {/* Product frame */}
          <div className="glass" style={{ marginTop: '3.5rem', padding: '.6rem', textAlign: 'left' }}>
            <div style={{ background: 'linear-gradient(180deg,#fbfaff,#f4f6fd)', borderRadius: 14, padding: '1.6rem', border: '1px solid rgba(11,16,32,0.05)' }}>
              <div style={{ display: 'flex', gap: '.4rem', marginBottom: '1.3rem' }}>
                {['#ef4444', '#f59e0b', '#10b981'].map(c => (
                  <span key={c} style={{ width: 10, height: 10, borderRadius: 99, background: c, opacity: .75 }} />
                ))}
              </div>
              <div className="grid g3">
                {[
                  { i: <Wand2 size={16} />, t: 'Creative brief written', s: 'One 10-second vertical shot, hook on frame one.', c: 'var(--violet)' },
                  { i: <Eye size={16} />, t: 'Caption drafted', s: 'From your brand profile and what the video shows.', c: 'var(--blue)' },
                  { i: <Send size={16} />, t: 'Published', s: 'Facebook ✓  Instagram ✓ — logged with the result.', c: 'var(--green)' },
                ].map(x => (
                  <div key={x.t} style={{ background: '#fff', borderRadius: 12, padding: '1.1rem', border: '1px solid rgba(11,16,32,0.07)' }}>
                    <div style={{ color: x.c, marginBottom: '.55rem' }}>{x.i}</div>
                    <div style={{ fontWeight: 660, fontSize: '.93rem', marginBottom: '.3rem' }}>{x.t}</div>
                    <p style={{ fontSize: '.83rem', lineHeight: 1.5 }}>{x.s}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Honest platform strip */}
          <div style={{ marginTop: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1.6rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '.74rem', letterSpacing: '.1em', textTransform: 'uppercase', color: 'var(--ink-faint)', fontWeight: 700 }}>
              One-click publishing
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '.45rem', fontWeight: 640 }}>
              <Facebook size={18} color="#1877F2" /> Facebook
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '.45rem', fontWeight: 640 }}>
              <Instagram size={18} color="#E4405F" /> Instagram
            </span>
            <span style={{ fontSize: '.8rem', color: 'var(--ink-faint)' }}>
              X and LinkedIn with your own API token
            </span>
          </div>
        </div>
      </section>

      {/* LIVE DEMO — the real writer, not a canned string */}
      <section id="try" style={{ paddingTop: '2rem' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <span className="eyebrow">Try it now</span>
            <h2 className="h2" style={{ margin: '1.1rem 0 .8rem' }}>Watch it write for your business</h2>
            <p className="lede" style={{ maxWidth: 560, margin: '0 auto' }}>
              This runs the same copywriter your posts use. No signup.
            </p>
          </div>

          <div className="glass" style={{ maxWidth: 780, margin: '0 auto', padding: '2rem' }}>
            <form onSubmit={runDemo} className="grid" style={{ gap: '.9rem' }}>
              <div className="grid g2" style={{ gap: '.9rem' }}>
                <input className="field" placeholder="Your business name" value={bizName}
                  onChange={e => setBizName(e.target.value)} required maxLength={80} />
                <select className="field" value={bizModel} onChange={e => setBizModel(e.target.value)}>
                  <option>SaaS</option><option>E-commerce</option>
                  <option>Agency</option><option>Local Business</option>
                  <option>Education</option><option>Health & Fitness</option>
                </select>
              </div>
              <input className="field" placeholder="What do you sell? (one line — the more specific, the better the copy)"
                value={bizDesc} onChange={e => setBizDesc(e.target.value)} maxLength={200} />
              <button type="submit" className="b b-primary" disabled={demoBusy} style={{ justifySelf: 'start', padding: '.85rem 1.6rem' }}>
                {demoBusy ? <>Writing…</> : <><Sparkles size={16} /> Write a caption</>}
              </button>
            </form>

            {demoErr && (
              <div style={{ marginTop: '1.4rem', padding: '.9rem 1rem', borderRadius: 12, background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)', display: 'flex', gap: '.5rem' }}>
                <AlertCircle size={16} color="#dc2626" style={{ flexShrink: 0, marginTop: 2 }} />
                <p style={{ fontSize: '.87rem', color: '#b91c1c', lineHeight: 1.5 }}>{demoErr}</p>
              </div>
            )}

            {demoOut && (
              <div style={{ marginTop: '1.6rem' }}>
                <div style={{ fontSize: '.72rem', fontWeight: 700, letterSpacing: '.09em', textTransform: 'uppercase', color: 'var(--ink-faint)', marginBottom: '.6rem' }}>
                  Written just now
                </div>
                <div style={{ background: '#fff', border: '1px solid rgba(11,16,32,0.09)', borderRadius: 14, padding: '1.3rem', whiteSpace: 'pre-wrap', fontSize: '.94rem', lineHeight: 1.65 }}>
                  {demoOut}
                </div>
                <button className="b b-primary" style={{ marginTop: '1.2rem', width: '100%' }} onClick={() => navigate('/auth')}>
                  Get this posting automatically — free <ArrowRight size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* HOW */}
      <section>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span className="eyebrow">No guesswork</span>
            <h2 className="h2" style={{ margin: '1.1rem 0 .8rem' }}>Your first ten minutes</h2>
            <p className="lede" style={{ maxWidth: 560, margin: '0 auto' }}>
              Exactly what happens, in order.
            </p>
          </div>

          <div className="grid g4">
            {[
              ['01', 'Paste your website', 'It reads your site and builds a brand profile — what you sell, who buys it, the words you use. About a minute.'],
              ['02', 'Connect Facebook & Instagram', 'One Meta login. Pick the Page and the Instagram account posts should land on.'],
              ['03', 'Review the first post', 'A caption written from your brand profile and the media attached. Edit it, or approve it.'],
              ['04', 'Switch on auto-approve', 'It publishes on your schedule from then on. Every delivery is logged with its result.'],
            ].map(([n, t, b]) => (
              <div key={n} className="glass glass-lift" style={{ padding: '1.75rem' }}>
                <div style={{ fontSize: '.78rem', fontWeight: 800, letterSpacing: '.1em', color: 'var(--violet)', marginBottom: '.7rem' }}>{n}</div>
                <h3 style={{ fontSize: '1.02rem', marginBottom: '.5rem', fontWeight: 680 }}>{t}</h3>
                <p style={{ fontSize: '.88rem', lineHeight: 1.6 }}>{b}</p>
              </div>
            ))}
          </div>

          {stats?.posts > 0 && (
            <p style={{ textAlign: 'center', marginTop: '2.5rem', fontSize: '.88rem', color: 'var(--ink-faint)' }}>
              <strong style={{ color: 'var(--ink)' }}>{stats.posts.toLocaleString()}</strong> posts generated on the platform so far
            </p>
          )}
        </div>
      </section>

      {/* WHY */}
      <section style={{ background: 'linear-gradient(180deg, rgba(139,92,246,0.05), rgba(37,99,235,0.04))' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span className="eyebrow">Why it is different</span>
            <h2 className="h2" style={{ margin: '1.1rem 0 .8rem' }}>Most AI writes filler. This does not.</h2>
          </div>

          <div className="grid g3">
            {[
              ['It knows what you sell', 'Captions are written from your website and the specific media attached — not from a category template. If a competitor could post the same caption, it gets rejected and rewritten.', 'var(--violet)'],
              ['Briefs a model can render', 'Creative briefs are built for what video models actually produce: one subject, one camera move, no unreadable interface text. That is the difference between a usable clip and a smeared one.', 'var(--blue)'],
              ['Nothing is a black box', 'Every prompt is saved next to the asset it produced. Every post shows where it went and why it failed if it did. You can always see what it did on your behalf.', 'var(--pink)'],
            ].map(([t, b, c]) => (
              <div key={t} className="glass glass-lift" style={{ padding: '1.9rem' }}>
                <div style={{ width: 38, height: 38, borderRadius: 11, background: `${c}14`, border: `1px solid ${c}2e`, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                  <CheckCircle2 size={18} color={c} />
                </div>
                <h3 style={{ fontSize: '1.06rem', marginBottom: '.55rem', fontWeight: 690 }}>{t}</h3>
                <p style={{ fontSize: '.9rem', lineHeight: 1.65 }}>{b}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="pricing">
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span className="eyebrow">Pricing</span>
            <h2 className="h2" style={{ margin: '1.1rem 0 .8rem' }}>Start free. Pay when it earns its keep.</h2>
            <p className="lede" style={{ maxWidth: 580, margin: '0 auto' }}>
              Run the whole pipeline on the free plan first. Upgrade when you want it posting daily.
            </p>
          </div>

          <div className="grid g4" style={{ alignItems: 'stretch' }}>
            {plans.map(p => {
              const free = p.price <= 0;
              const hero = p.code === 'starter';
              return (
                <div key={p.code} className="glass glass-lift" style={{
                  padding: '2rem 1.6rem', display: 'flex', flexDirection: 'column', position: 'relative',
                  border: hero ? '1.5px solid rgba(109,40,217,0.42)' : undefined,
                  boxShadow: hero ? '0 20px 50px -18px rgba(109,40,217,0.42)' : undefined,
                }}>
                  {hero && <div className="price-pop">MOST POPULAR</div>}
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, color: hero ? 'var(--violet)' : 'var(--ink)' }}>{p.name}</h3>
                  <div style={{ margin: '.7rem 0 .3rem', fontSize: '2.3rem', fontWeight: 780, lineHeight: 1 }}>
                    {free ? 'Free' : <>
                      <span style={{ fontSize: '1.2rem', verticalAlign: 'super', fontWeight: 640 }}>$</span>{p.price}
                      <span style={{ fontSize: '.9rem', fontWeight: 500, color: 'var(--ink-faint)' }}>/mo</span>
                    </>}
                  </div>
                  <p style={{ fontSize: '.85rem', lineHeight: 1.55, minHeight: 42, marginBottom: '1.3rem' }}>{p.tagline}</p>

                  <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1.7rem', display: 'grid', gap: '.6rem', flex: 1 }}>
                    {p.features.map(f => (
                      <li key={f} style={{ display: 'flex', gap: '.5rem', fontSize: '.86rem', lineHeight: 1.5 }}>
                        <CheckCircle2 size={15} color="var(--green)" style={{ flexShrink: 0, marginTop: 2 }} />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>

                  <button className={`b ${hero ? 'b-primary' : 'b-ghost'}`} style={{ width: '100%' }} onClick={() => navigate('/auth')}>
                    {free ? 'Start free' : `Choose ${p.name}`}
                  </button>
                </div>
              );
            })}
          </div>

          <div style={{ textAlign: 'center', marginTop: '2.5rem', display: 'grid', gap: '.5rem' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '.5rem', color: 'var(--green)', fontSize: '.9rem', fontWeight: 620 }}>
              <ShieldCheck size={16} /> Billed monthly through PayPal · cancel any time
            </span>
            <span style={{ fontSize: '.84rem', color: 'var(--ink-faint)' }}>
              Cancelling keeps your access to the end of the period you already paid for. We never see or store card details.
            </span>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section style={{ paddingTop: '2rem' }}>
        <div className="wrap" style={{ maxWidth: 780 }}>
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <span className="eyebrow">Questions</span>
            <h2 className="h2" style={{ margin: '1.1rem 0 0' }}>Before you sign up</h2>
          </div>

          {faqs.map(([q, a], i) => (
            <div key={q} className="faq">
              <button onClick={() => setOpenFaq(openFaq === i ? null : i)}>
                {q}
                <ChevronDown size={18} style={{ flexShrink: 0, color: 'var(--ink-faint)', transform: openFaq === i ? 'rotate(180deg)' : 'none', transition: 'transform .25s' }} />
              </button>
              <div className={`a ${openFaq === i ? 'open' : ''}`}>
                <p style={{ paddingBottom: '1.35rem', fontSize: '.93rem', lineHeight: 1.7 }}>{a}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CLOSE */}
      <section>
        <div className="wrap">
          <div className="glass" style={{ padding: 'clamp(2.5rem,5vw,4rem)', textAlign: 'center', background: 'linear-gradient(135deg, rgba(109,40,217,0.10), rgba(37,99,235,0.08))' }}>
            <h2 className="h2" style={{ maxWidth: 620, margin: '0 auto' }}>
              Set it up once. <span className="tint">Then get on with your work.</span>
            </h2>
            <p className="lede" style={{ maxWidth: 500, margin: '1.2rem auto 2rem' }}>
              Free plan, no card. Ten minutes to your first reviewed post.
            </p>
            <button className="b b-primary" style={{ padding: '1rem 2.1rem', fontSize: '1.02rem' }} onClick={() => navigate('/auth')}>
              Start free <ArrowRight size={17} />
            </button>
            <p style={{ fontSize: '.83rem', color: 'var(--ink-faint)', marginTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '.4rem' }}>
              <Clock size={13} /> Auto-approve is off until you turn it on
            </p>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ borderTop: '1px solid var(--line)', padding: '2.5rem 0', background: 'rgba(255,255,255,0.6)' }}>
        <div className="wrap" style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div className="brand" style={{ fontSize: '1rem' }}>
            <Sparkles size={17} color="#6d28d9" /> OrganicAI
          </div>
          <div style={{ display: 'flex', gap: '1.4rem', fontSize: '.85rem' }}>
            <a href="/privacy" style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>Privacy</a>
            <a href="/terms" style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>Terms</a>
            <a href="/dpa" style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>DPA</a>
          </div>
          <span style={{ fontSize: '.82rem', color: 'var(--ink-faint)' }}>
            © {new Date().getFullYear()} OrganicAI
          </span>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
