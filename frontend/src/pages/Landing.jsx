import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2, Sparkles, ArrowRight, ChevronDown, ShieldCheck,
  Instagram, Facebook, Wand2, Clock, Eye, Send, AlertCircle,
  MonitorSmartphone, ShoppingBag, Bot, Layers, Store, GraduationCap, Building2,
  Flame, Zap, TrendingUp, BarChart3, Repeat, Heart, MessageSquare,
  ArrowUp, ThumbsUp, Radio, Film, Volume2, Share2, Copy
} from 'lucide-react';
import { Helmet } from 'react-helmet-async';

import AccountsMarquee from '../components/AccountsMarquee';
import ReviewWall from '../components/ReviewWall';
import Logo from '../components/Logo';
import CardRail from '../components/CardRail';
import CountUp from '../components/CountUp';
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
  /* clip, NOT hidden. Setting overflow-x to hidden forces overflow-y to
     compute to auto -- the spec does not allow one axis to clip while the
     other stays visible -- which quietly turns this element into a scroll
     container. That put every section below the fold outside the viewport's
     intersection chain, so IntersectionObserver never fired and the scroll
     reveals stayed invisible. clip clips without creating a scroll container.
     (No backticks anywhere in this stylesheet: it is a template literal.) */
  overflow-x: clip;
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

.omai, .omai p, .omai button, .omai input, .omai select, .omai a {
  font-family: 'Manrope', system-ui, sans-serif;
}
.omai h1, .omai h2, .omai h3, .omai .brand, .omai .h1, .omai .h2 {
  font-family: 'Bricolage Grotesque', system-ui, sans-serif;
  font-optical-sizing: auto;
}
.omai h1, .omai h2, .omai h3 {
  color: var(--ink); letter-spacing: -0.03em; margin: 0;
  text-wrap: balance;
}
/* max-width keeps running text near a readable measure. margin-inline: auto
   is not optional alongside it: without it a constrained paragraph inside a
   centred section is capped at 68ch and then sits hard LEFT of its container,
   because text-align centres the text inside the box and does nothing to
   place the box itself. That broke the stat caption and several section
   subheads the moment the measure was introduced.
   Where a paragraph is already narrower than its container the auto margins
   have no effect, so this is safe for the left-aligned card copy too. */
.omai p { color: var(--ink-soft); margin: 0; max-width: 68ch; margin-inline: auto; }
/* Digits that line up wherever a figure is the point. */
.omai .tnum { font-variant-numeric: tabular-nums; }
/* 6rem left long dead bands between sections, which reads as a slow page and
   costs scroll depth. Tighter keeps the argument moving. */
.omai section { padding: 3.6rem 0; }

/* Sections lift in as they enter the viewport. Movement earns attention on a
   long page, and a section that arrives is read more than one already sitting
   there when you get to it.
   Short, single-direction and once only: repeating on every scroll past is
   what makes this kind of thing feel cheap, and content that animates out
   again is content someone has to wait for twice.
   The hidden state applies ONLY once JS has added .js-ready, so if the
   observer never runs the page still renders fully rather than blank.
   (No backticks in here: this block lives inside a template literal.) */
.omai.js-ready .reveal {
  opacity: 0;
  transform: translateY(22px);
  transition: opacity .62s cubic-bezier(.4,0,.2,1), transform .62s cubic-bezier(.4,0,.2,1);
  will-change: opacity, transform;
}
.omai.js-ready .reveal.in { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  .omai.js-ready .reveal { opacity: 1; transform: none; transition: none; }
}
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
/* Full width, not the 1180px content column. A bar that stops short of the
   window edge reads as a page inside a page; the mark hard left and the
   action hard right is what enterprise software looks like, and it puts the
   primary button in the corner the eye finishes on. */
.omai .nav-in {
  width: 100%; padding: .78rem clamp(1.1rem, 3.5vw, 2.75rem);
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  box-sizing: border-box;
}
.omai .brand {
  display: flex; align-items: center; gap: .55rem;
  font-weight: 750; font-size: 1.1rem; cursor: pointer; letter-spacing: -.021em;
  margin-right: auto;
}
.omai .nav-actions { display: flex; align-items: center; gap: .55rem; margin-left: auto; }

.omai .grid { display: grid; gap: 1.25rem; }
.omai .g2 { grid-template-columns: repeat(auto-fit, minmax(300px,1fr)); }
.omai .g3 { grid-template-columns: repeat(auto-fit, minmax(260px,1fr)); }
.omai .g4 { grid-template-columns: repeat(auto-fit, minmax(230px,1fr)); }

.omai .h1 { font-size: clamp(2.5rem, 5.4vw, 4rem); line-height: 1.04; font-weight: 780; }
.omai .h2 { font-size: clamp(1.9rem, 3.2vw, 2.6rem); line-height: 1.12; font-weight: 740; }
.omai .lede { font-size: clamp(1.02rem, 1.35vw, 1.18rem); line-height: 1.62; }
/* One colour, not three.
   A violet-to-blue-to-pink gradient across a headline is the single most
   common tell of a generated page, and it spends the page's whole colour
   budget in the first three seconds. The headline now carries one accent
   hue, which leaves the primary button as the only other saturated thing
   above the fold -- so the eye goes to the button. */
.omai .tint { color: var(--violet); }

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

/* Phones. This block used to set section padding to 4rem, which is MORE than
   the 3.6rem desktop default -- the smaller screen was getting the larger
   dead bands, so the argument took longer to scroll through on the device
   where scrolling costs most. */
@media (max-width: 720px) {
  .omai section { padding: 2.6rem 0; }
  .omai .wrap { padding: 0 1.15rem; }

  /* The headline is the hook and it should not need three scrolls to read.
     Tighter tracking at this size keeps a long line on two rows. */
  .omai .h1 { font-size: clamp(2.05rem, 8.6vw, 2.6rem); letter-spacing: -.035em; }
  .omai .h2 { font-size: clamp(1.55rem, 6.4vw, 1.95rem); }
  .omai .lede { font-size: 1rem; line-height: 1.58; }

  /* Full-width and thumb-sized. A centred pill button on a phone reads as a
     link people are not sure is tappable. */
  .omai .b { width: 100%; min-height: 48px; padding: .95rem 1.25rem; }
  .omai .nav-actions .b { width: auto; min-height: 40px; padding: .5rem .9rem; }

  /* The nav carries a mark and two actions across 375px. Without this the
     brand tagline pushes the primary button off the right edge. */
  .omai .nav-in { padding: .6rem .9rem; gap: .5rem; }
  .omai .brand { font-size: 1rem; min-width: 0; }
  /* The lockup is sized for a desktop bar. At 46px plus a strapline it made
     the mobile nav 82px tall -- a tenth of the screen, before the page has
     said anything. The mark shrinks and the strapline goes: the page title
     already says what this is, twice. */
  .omai .brand img { width: 32px !important; height: 32px !important; }
  .omai .logo-tagline { display: none; }
  .omai .logo-wordmark { font-size: 1.25rem !important; }

  /* The bar holds a lockup and two actions across 375px. Over budget, the
     buttons were the thing that gave -- "Start free" wrapped onto two lines
     and took the nav to 82px. They keep their words on one line now and the
     lockup gives up the width instead. */
  .omai .nav-actions .b { white-space: nowrap; font-size: .85rem; padding: .5rem .8rem !important; }

  /* Cards carrying desktop padding waste a third of the width. */
  .omai .glass { border-radius: 14px; }
  .omai .grid { gap: .9rem; }
}
`;


/* The ask, repeated where conviction happens.
   The page ran 660 lines between the hero button and the pricing button, so a
   reader persuaded by the problem or by the faceless engine had to scroll past
   eight sections to act on it. Conviction decays over that distance. This is
   the same destination and the same words -- repeating one ask keeps the
   page's single-CTA discipline, whereas a second offer would split it. */
const InlineCTA = ({ line, onStart }) => (
  <section style={{ paddingTop: '1rem', paddingBottom: '1rem' }}>
    <div className="wrap" style={{ textAlign: 'center' }}>
      <div className="glass" style={{ padding: '1.9rem 1.5rem' }}>
        <p style={{ fontSize: '1.05rem', fontWeight: 640, color: 'var(--ink)', marginBottom: '1.1rem' }}>
          {line}
        </p>
        <button className="b b-primary" style={{ padding: '.95rem 2.1rem', fontSize: '1rem' }} onClick={onStart}>
          Start free <ArrowRight size={16} />
        </button>
        <p style={{ fontSize: '.82rem', color: 'var(--ink-faint)', marginTop: '.8rem' }}>
          Free plan · no card · nothing publishes until you allow it
        </p>
      </div>
    </div>
  </section>
);

const Landing = () => {
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState(null);
  const [stats, setStats] = useState(null);
  const rootRef = React.useRef(null);

  // Reveal each section as it scrolls into view.
  //
  // The hidden state is applied by JS (`js-ready`) rather than sitting in the
  // stylesheet, so a browser that never runs this effect shows the whole page
  // instead of a blank one. That failure mode is worth the extra class: a
  // landing page that renders empty sells nothing at all.
  //
  // Unobserved after firing, so nothing animates twice and the observer is
  // not carrying every section for the life of the page.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;

    const targets = Array.from(root.querySelectorAll('section > .wrap'));
    if (!targets.length || typeof IntersectionObserver === 'undefined') {
      return undefined;
    }

    root.classList.add('js-ready');
    targets.forEach((el) => el.classList.add('reveal'));

    // The hero is above the fold and must never wait for a scroll event that
    // may never come.
    if (targets[0]) targets[0].classList.add('in');

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('in');
          observer.unobserve(entry.target);
        });
      },
      // Fires a little before the section is fully on screen, so it has
      // finished arriving by the time it is being read.
      { threshold: 0.08, rootMargin: '0px 0px -8% 0px' }
    );

    targets.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

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

  const entry = Math.min(...plans.filter(p => !p.custom && p.price > 0).map(p => p.price), 17);

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
    ['Can I generate faceless short videos on auto-pilot?',
     'Yes. Pick from 5 ready-made viral topics (Scary Stories, Jokes & Comedy, Life Pro Tips, Today I Learned, You Should Know) or bring your own custom topic. Choose a visual style and AI voice persona, and the system writes the hook, voiceover, diffusion prompts, and publishes 8s–30s shorts on your schedule.'],
    ['What is the Viral Validator and view predictor?',
     'We reverse-engineered algorithmic triggers across 500M+ shorts. It scores any video on 5 metrics (Hook Performance, Retention Rate, Shareability, Likeability, Commentability) with timestamped "Fix The Fail" alerts and 1-click AI algorithmic rewrites.'],
    ['How does PostShip multi-platform repurposing work?',
     'Paste any idea, changelog line, or product URL. PostShip automatically writes 3 native variations for X (punchy build-in-public), LinkedIn (story-driven founder insight), and Reddit (authentic builder story with target subreddit). No generic copy-pasting.'],
    ['Does anything post without my approval?',
     'No. Auto-approve is off by default. Every generated post waits in a review log where you can edit or delete it. You can also send videos to TikTok Drafts or publish as Private / Unlisted before going live.'],
    ['Which platforms does it publish to?',
     'Facebook Pages, Instagram (including Reels), YouTube Shorts, TikTok, X (Twitter), and LinkedIn.'],
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
    <div className="omai" ref={rootRef}>
      <style>{styles}</style>
      <Helmet>
        <title>Organiflo — Organic marketing that runs itself</title>
        <meta name="description" content="AI writes brand-matched social posts and publishes them to your Facebook Page and Instagram on a schedule you set. Free plan, no card required." />
        <script type="application/ld+json">{JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'SoftwareApplication',
          name: 'Organiflo',
          applicationCategory: 'BusinessApplication',
          offers: { '@type': 'Offer', price: String(entry), priceCurrency: 'USD' },
          description: 'Automated organic marketing for small businesses',
        })}</script>
      </Helmet>

      {/* NAV */}
      <nav className="nav">
        <div className="nav-in">
          <div className="brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <Logo size={46} showWordmark />
          </div>
          <div className="nav-actions">
            <button className="b b-ghost" style={{ padding: '.6rem 1rem' }} onClick={() => navigate('/auth')}>Log in</button>
            <button className="b b-primary" style={{ padding: '.6rem 1.15rem' }} onClick={() => navigate('/auth')}>Start free</button>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section style={{ paddingTop: '5rem', paddingBottom: '4rem' }}>
        <div className="wrap" style={{ textAlign: 'center' }}>
          <span className="eyebrow"><Sparkles size={13} /> Free plan · no card</span>

          {/* Pain first, not benefit first.
              This read "Your marketing runs while you run the business" — true,
              but it is the destination, and a visitor arriving cold from an ad
              has not yet agreed there is a problem to solve. A benefit
              headline asks someone to want something; a loss headline asks
              them to recognise something, and recognition is the cheaper ask.
              The old line is not wasted — it is the answer, so it moved down
              one level to the lede where it now lands as a resolution. */}
          <h1 className="h1" style={{ margin: '1.4rem auto 0', maxWidth: 940 }}>
            Posting every day is a full-time job.<br />
            <span className="tint">You already have one.</span>
          </h1>

          <p className="lede" style={{ maxWidth: 640, margin: '1.5rem auto 0' }}>
            So Organiflo does it. Add your website once — it learns what you sell, writes the
            copy and the creative brief, and publishes to your Facebook Page and Instagram on
            the schedule you set. Your marketing runs while you run the business.
          </p>

          {/* One action, not two.
              The second button pointed at #try, which was the live-demo
              section — removed earlier, so it had become a button that
              scrolled nowhere. Beyond being broken it was splitting the
              decision: a secondary CTA beside the primary one gives the
              visitor a way to not decide, and "watch a demo" is exactly the
              path that ends in a closed tab. There is one thing to do here. */}
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2.2rem' }}>
            <button className="b b-primary" style={{ padding: '1.05rem 2.4rem', fontSize: '1.04rem' }} onClick={() => navigate('/auth')}>
              Start free <ArrowRight size={17} />
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

      {/* LIVE ACCOUNTS — real profiles, clickable, growing as customers connect.
          Placed directly under the hero because it is the evidence for the
          claim the hero just made. Renders nothing if none come back. */}
      <section style={{ padding: '0 0 3.5rem' }}>
        <AccountsMarquee />
      </section>

      {/* THE PROBLEM */}
      <section style={{ background: 'linear-gradient(180deg, rgba(219,39,119,0.045), rgba(139,92,246,0.04))' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span className="eyebrow" style={{ color: 'var(--pink)', background: 'rgba(219,39,119,0.09)', borderColor: 'rgba(219,39,119,0.2)' }}>
              The problem
            </span>
            <h2 className="h2" style={{ margin: '1.1rem auto .9rem', maxWidth: 760 }}>
              Every business now needs a media team it cannot afford.
            </h2>
            <p className="lede" style={{ maxWidth: 660, margin: '0 auto' }}>
              Reach used to come from paying for it. Now it comes from posting constantly,
              on platforms that reward volume and punish gaps. That is a full-time job
              nobody hired for.
            </p>
          </div>

          <div className="grid g3">
            {[
              ['The output nobody has time for',
               'Short video is what actually reaches people, and it needs a concept, a script, an edit and a caption. Every post. Forever. Most owners manage two weeks and stop.'],
              ['The gap that costs you',
               'Miss a week and reach collapses, and it does not come back when you return. Consistency is the whole mechanic, and consistency is exactly what a busy operator cannot give it.'],
              ['The help that does not fit',
               'An agency is $2,000 a month and still needs briefing. Generic AI tools write copy that could belong to any competitor, because they were never told what you actually sell.'],
            ].map(([t, b]) => (
              <div key={t} className="glass" style={{ padding: '1.9rem' }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(219,39,119,0.09)', border: '1px solid rgba(219,39,119,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                  <AlertCircle size={17} color="var(--pink)" />
                </div>
                <h3 style={{ fontSize: '1.03rem', marginBottom: '.55rem', fontWeight: 690 }}>{t}</h3>
                <p style={{ fontSize: '.89rem', lineHeight: 1.65 }}>{b}</p>
              </div>
            ))}
          </div>

          <div className="glass" style={{ marginTop: '2rem', padding: '1.6rem 1.9rem', display: 'flex', gap: '1rem', alignItems: 'flex-start', background: 'rgba(255,255,255,0.85)' }}>
            <CheckCircle2 size={20} color="var(--green)" style={{ flexShrink: 0, marginTop: 2 }} />
            <p style={{ fontSize: '.97rem', lineHeight: 1.65, color: 'var(--ink)' }}>
              <strong>What we built instead:</strong> a system that learns one business properly
              — what it sells, who buys it, the words it uses — and then does the whole loop
              on its own. Brief, creative, caption, publish, log. You review what you want to
              review and ignore the rest.
            </p>
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

          {/* The one number on the page that is checkable and grows on its own.
              It was set at footnote size, which wasted it. */}
          {stats?.posts > 0 && (
            <div style={{ textAlign: 'center', marginTop: '3.2rem' }}>
              <CountUp
                value={stats.posts}
                style={{
                  display: 'block',
                  fontSize: 'clamp(3.2rem, 8vw, 5.6rem)',
                  fontWeight: 800,
                  lineHeight: 1,
                  letterSpacing: '-.045em',
                  background: 'linear-gradient(120deg, var(--violet), var(--blue) 55%, var(--pink))',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              />
              <p style={{
                marginTop: '.7rem', fontSize: '.8rem', fontWeight: 700,
                letterSpacing: '.12em', textTransform: 'uppercase',
                color: 'var(--ink-faint)',
              }}>
                posts published so far — and counting
              </p>
            </div>
          )}
        </div>
      </section>

      <InlineCTA
        line="Ten minutes to set up. Then it posts without you."
        onStart={() => navigate('/auth')}
      />

      {/* FEATURES */}
      <section style={{ background: 'linear-gradient(180deg, rgba(37,99,235,0.045), rgba(139,92,246,0.04))' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span className="eyebrow">What you get</span>
            <h2 className="h2" style={{ margin: '1.1rem auto .9rem', maxWidth: 700 }}>
              The whole loop, not just the writing part
            </h2>
            <p className="lede" style={{ maxWidth: 600, margin: '0 auto' }}>
              Most tools hand you a draft and leave the rest to you. This one carries it
              all the way to a published post and tells you what happened.
            </p>
          </div>

          {/* A rail rather than a grid: six cards in a four-wide grid leave an
              orphaned row of two, which reads as an unfinished section. */}
          <CardRail
            items={[
              { key: 'brand', icon: <Sparkles size={17} />, title: 'Brand profile from your site',
                body: 'It reads your website and builds what it needs: what you sell, who buys it, your tone, your content themes, your offer. Every asset after that is written from it.', colour: 'var(--violet)' },
              { key: 'briefs', icon: <Wand2 size={17} />, title: 'Creative briefs a model can render',
                body: 'Ten-second vertical shots built for what video models actually produce — one subject, one camera move, no unreadable interface text. Copy the brief into Veo, Flow, Runway or Kling.', colour: 'var(--blue)' },
              { key: 'captions', icon: <Eye size={17} />, title: 'Captions that know the visual',
                body: 'Each caption is written from your brand profile plus a description of the specific asset attached, so it speaks to what is on screen instead of the category in general.', colour: 'var(--pink)' },
              { key: 'publish', icon: <Send size={17} />, title: 'Publishing with a real delivery log',
                body: 'Facebook Pages and Instagram, including Reels. Every attempt is recorded per platform with the reason if it failed — no post that silently went nowhere.', colour: 'var(--green)' },
              { key: 'schedule', icon: <Clock size={17} />, title: 'Runs on your schedule',
                body: 'Every two hours, or whatever interval you choose. Auto-approve is off until you switch it on, so nothing reaches an audience you have not approved.', colour: 'var(--violet)' },
              { key: 'email', icon: <CheckCircle2 size={17} />, title: 'Email campaigns from the same brain',
                body: 'Drafts written from the same profile, sent from your own domain, to your own subscriber list — with edit and preview before anything goes out.', colour: 'var(--blue)' },
            ]}
            renderItem={({ icon, title, body, colour }) => (
              <div className="glass glass-lift" style={{ padding: '1.85rem', height: '100%', boxSizing: 'border-box' }}>
                <div style={{ width: 38, height: 38, borderRadius: 11, background: `${colour}14`, border: `1px solid ${colour}2e`, color: colour, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
                  {icon}
                </div>
                <h3 style={{ fontSize: '1.02rem', marginBottom: '.55rem', fontWeight: 690 }}>{title}</h3>
                <p style={{ fontSize: '.88rem', lineHeight: 1.65 }}>{body}</p>
              </div>
            )}
          />
        </div>
      </section>

      {/* BUSINESS TYPES */}
      <section>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <span className="eyebrow">Built for how you sell</span>
            <h2 className="h2" style={{ margin: '1.1rem auto .9rem', maxWidth: 720 }}>
              A SaaS and a skincare brand should not post the same way
            </h2>
            <p className="lede" style={{ maxWidth: 620, margin: '0 auto' }}>
              Pick your model at setup and the pipeline changes behind it — the creative
              direction, the framework the copy uses, and where the subject comes from.
            </p>
          </div>

          <CardRail
            interval={3900}
            items={[
              { key: 'faceless', icon: <Zap size={18} />, title: 'Faceless Channel', colour: '#f97316',
                body: 'Dedicated faceless video brand on auto-pilot. Generates 8s–30s scroll-stopping hooks, voiceover scripts, Midjourney start frames, Kling/Veo motion diffusion prompts, outro cards, and publishes directly to YouTube Shorts, TikTok, & Reels.' },
              { key: 'saas', icon: <MonitorSmartphone size={18} />, title: 'SaaS & Data', colour: 'var(--blue)',
                body: 'Software is the hardest thing to film, because the interface is what models cannot draw. So it films the person — the second the result lands, the shoulders dropping. Screens appear only as light on a face.' },
              { key: 'ecom', icon: <ShoppingBag size={18} />, title: 'E-commerce', colour: 'var(--violet)',
                body: 'Point it at your product feed and it rotates through your catalog, one product at a time, writing problem-solution copy against that product\'s own details rather than your brand blurb.' },
              { key: 'influencer', icon: <Bot size={18} />, title: 'AI Influencer', colour: 'var(--pink)',
                body: 'Writes in first person as the persona, not as a company. Keep a character reference on file and the visuals stay recognisably the same face across posts.' },
              { key: 'agency', icon: <Layers size={18} />, title: 'Creators & Agencies', colour: 'var(--green)',
                body: 'Run several brands from one login, each with its own profile, media library, connected accounts and schedule. Nothing bleeds between them.' },
              { key: 'local', icon: <Store size={18} />, title: 'Local Business', colour: 'var(--violet)',
                body: 'Real places and real hands rather than stock polish. The creative direction leans on materials, light and the moment a customer reacts — which is what these models render best.' },
              { key: 'education', icon: <GraduationCap size={18} />, title: 'Education & Coaching', colour: 'var(--blue)',
                body: 'The strongest shot is the face at the moment of understanding, not a graduation stock photo. Copy leads with the specific thing someone will be able to do.' },
            ]}
            renderItem={({ icon, title, colour, body }) => (
              <div className="glass glass-lift" style={{ padding: '1.85rem', height: '100%', boxSizing: 'border-box' }}>
                <div style={{
                  width: 38, height: 38, borderRadius: 11,
                  background: `${colour}14`, border: `1px solid ${colour}2e`, color: colour,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  marginBottom: '1rem',
                }}>
                  {icon}
                </div>
                <h3 style={{ fontSize: '1.04rem', marginBottom: '.55rem', fontWeight: 690, color: colour }}>{title}</h3>
                <p style={{ fontSize: '.88rem', lineHeight: 1.65 }}>{body}</p>
              </div>
            )}
          />

          <p style={{ textAlign: 'center', marginTop: '2.2rem', fontSize: '.88rem', color: 'var(--ink-faint)' }}>
            Not on the list? The general pipeline handles any business with a website — the
            profile is built from your own words either way.
          </p>
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

      {/* ========================================================================= */}
      <InlineCTA
        line="Your business, in its own words, on your schedule."
        onStart={() => navigate('/auth')}
      />

      {/* ENTERPRISE SHOWCASE 1: FACELESS SHORT VIDEOS ON AUTO-PILOT */}
      {/* ========================================================================= */}
      <section style={{ background: 'linear-gradient(180deg, rgba(249,115,22,0.05), rgba(139,92,246,0.04))' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.25rem 0.85rem',
              borderRadius: 20,
              background: 'rgba(249,115,22,0.15)',
              border: '1px solid rgba(249,115,22,0.35)',
              fontSize: '0.76rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '.06em',
              color: '#f97316',
              marginBottom: '1rem',
            }}>
              <Zap size={13} color="#f97316" /> Autonomous Channel Growth
            </span>
            <h2 style={{ fontSize: 'clamp(2rem, 4vw, 2.8rem)', fontWeight: 900, letterSpacing: '-0.03em', color: 'var(--ink)', margin: '0 0 1rem' }}>
              Faceless Short Videos on Auto-Pilot
            </h2>
            <p style={{ fontSize: '1.05rem', color: 'var(--ink-soft)', maxWidth: 680, margin: '0 auto', lineHeight: 1.6 }}>
              Pick a topic, pick a voice, pick a schedule. We write the hook, voiceover, keyframe image prompt, video diffusion prompt, and post every video for you.
            </p>
          </div>

          {/* 5 Topic Cards Showcase */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2.5rem' }}>
            {[
              { icon: '👻', title: 'Scary Stories', badge: 'Viral Suspense', desc: 'Chilling urban legends & paranormal mysteries' },
              { icon: '😂', title: 'Jokes & Comedy', badge: 'High Engagement', desc: 'Hilarious stand-up & relatable everyday humor' },
              { icon: '💡', title: 'Life Pro Tips', badge: 'High Saves', desc: 'Psychology hacks & unfair life advantages' },
              { icon: '🧠', title: 'Today I Learned', badge: 'High Shares', desc: 'Mind-blowing historical & real-world facts' },
              { icon: '⚠️', title: 'You Should Know', badge: 'Must Watch', desc: 'Crucial safety advice & hidden life secrets' },
            ].map(t => (
              <div key={t.title} style={{
                background: 'rgba(255,255,255,0.03)',
                borderRadius: 14,
                padding: '1.25rem',
                border: '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                    <span style={{ fontSize: '1.6rem' }}>{t.icon}</span>
                    <span style={{ fontSize: '0.65rem', fontWeight: 800, padding: '0.15rem 0.5rem', borderRadius: 6, background: 'rgba(249,115,22,0.2)', color: '#fb923c' }}>{t.badge}</span>
                  </div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--ink)', marginBottom: '0.35rem' }}>{t.title}</div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--ink-soft)', lineHeight: 1.45, margin: 0 }}>{t.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* 3 Pipeline Pillars (Visual Styles, Voices, Timed Video) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
            <div className="glass" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', color: '#f97316' }}>
                <Film size={18} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--ink)' }}>6 Visual Styles</h3>
              </div>
              <p style={{ fontSize: '0.84rem', color: 'var(--ink-soft)', lineHeight: 1.5, margin: 0 }}>
                Cinematic Realism (8K 35mm film), Cyberpunk Anime, Retro Comic, Vintage 35mm Film, 3D Gaming Motion, and Minimal 3D Pixar.
              </p>
            </div>

            <div className="glass" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', color: '#38bdf8' }}>
                <Volume2 size={18} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--ink)' }}>5 AI Voice Personas</h3>
              </div>
              <p style={{ fontSize: '0.84rem', color: 'var(--ink-soft)', lineHeight: 1.5, margin: 0 }}>
                Adam (Deep Storyteller), Rachel (Energetic Host), Marcus (Authoritative Guide), Bella (Warm Conversationalist), and Shadow Whisper.
              </p>
            </div>

            <div className="glass" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', color: '#10b981' }}>
                <Clock size={18} />
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--ink)' }}>8s to 30s Timed Scripts</h3>
              </div>
              <p style={{ fontSize: '0.84rem', color: 'var(--ink-soft)', lineHeight: 1.5, margin: 0 }}>
                Front-loaded 0-3s scroll-stopping hooks with timed pacing cues, Midjourney start frames, and Kling/Veo diffusion prompts.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* ENTERPRISE SHOWCASE 2: VIRAL VALIDATOR & ALGORITHM PREDICTOR */}
      {/* ========================================================================= */}
      <section style={{ background: 'linear-gradient(180deg, rgba(37,99,235,0.05), rgba(139,92,246,0.04))' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.25rem 0.85rem',
              borderRadius: 20,
              background: 'rgba(239,68,68,0.15)',
              border: '1px solid rgba(239,68,68,0.35)',
              fontSize: '0.76rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '.06em',
              color: '#f87171',
              marginBottom: '1rem',
            }}>
              <Flame size={13} color="#f87171" /> Algorithmic View Prediction
            </span>
            <h2 style={{ fontSize: 'clamp(2rem, 4vw, 2.8rem)', fontWeight: 900, letterSpacing: '-0.03em', color: 'var(--ink)', margin: '0 0 1rem' }}>
              Stop Guessing. Predict Views Before You Hit Upload.
            </h2>
            <p style={{ fontSize: '1.05rem', color: 'var(--ink-soft)', maxWidth: 680, margin: '0 auto', lineHeight: 1.6 }}>
              We reverse-engineered the viral code across 500M+ shorts. We score your content on the 5 metrics that actually trigger the algorithm.
            </p>
          </div>

          {/* 5-Metric Radar Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1rem', marginBottom: '2.5rem' }}>
            {[
              { title: 'Hook Performance', score: '95', desc: 'Visual & audio hook strength in first 3s to stop the scroll.' },
              { title: 'Retention Rate', score: '82', desc: 'Drop-off curve simulation to predict completion rate.' },
              { title: 'Shareability', score: '78', desc: 'Relatable triggers & high value density worth sending.' },
              { title: 'Likeability', score: '80', desc: 'Sentiment analysis for instant emotional resonance.' },
              { title: 'Commentability', score: '88', desc: 'Engagement friction & curiosity gaps that spark debates.' },
            ].map(m => (
              <div key={m.title} style={{
                background: 'rgba(255,255,255,0.03)',
                borderRadius: 14,
                padding: '1.25rem',
                border: '1px solid rgba(255,255,255,0.08)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--ink)' }}>{m.title}</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 900, color: '#10b981' }}>{m.score}%</span>
                </div>
                <p style={{ fontSize: '0.76rem', color: 'var(--ink-soft)', lineHeight: 1.45, margin: 0 }}>{m.desc}</p>
              </div>
            ))}
          </div>

          {/* 3 Creator Value Pillars */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
            <div className="glass" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#f87171' }}>
                <Eye size={18} />
                <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 800, color: 'var(--ink)' }}>Stop Posting Blindly</h3>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--ink-soft)', lineHeight: 1.5, margin: 0 }}>
                Know exactly how your video will perform before you hit upload.
              </p>
            </div>

            <div className="glass" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#f59e0b' }}>
                <Sparkles size={18} />
                <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 800, color: 'var(--ink)' }}>Fix Issues Instantly</h3>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--ink-soft)', lineHeight: 1.5, margin: 0 }}>
                Actionable feedback: "Shorten the intro", "Add visual cut at 0:04", "Boost audio".
              </p>
            </div>

            <div className="glass" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#10b981' }}>
                <TrendingUp size={18} />
                <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 800, color: 'var(--ink)' }}>Scale Your Growth</h3>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--ink-soft)', lineHeight: 1.5, margin: 0 }}>
                Consistent viral hits mean faster monetization and exponential organic reach.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* ENTERPRISE SHOWCASE 3: POSTSHIP MULTI-PLATFORM REPURPOSING */}
      {/* ========================================================================= */}
      <section style={{ background: 'linear-gradient(180deg, rgba(219,39,119,0.045), rgba(37,99,235,0.04))' }}>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.25rem 0.85rem',
              borderRadius: 20,
              background: 'rgba(59,130,246,0.15)',
              border: '1px solid rgba(59,130,246,0.35)',
              fontSize: '0.76rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '.06em',
              color: '#60a5fa',
              marginBottom: '1rem',
            }}>
              <Send size={13} color="#60a5fa" /> PostShip Multi-Platform Engine
            </span>
            <h2 style={{ fontSize: 'clamp(2rem, 4vw, 2.8rem)', fontWeight: 900, letterSpacing: '-0.03em', color: 'var(--ink)', margin: '0 0 1rem' }}>
              One click. Every platform, natively.
            </h2>
            <p style={{ fontSize: '1.05rem', color: 'var(--ink-soft)', maxWidth: 680, margin: '0 auto', lineHeight: 1.6 }}>
              The same ship line or product URL, rewritten for how each platform actually reads — not copy-pasted three times.
            </p>
          </div>

          {/* 3 Native Platform Cards Preview */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
            {/* X Card */}
            <div style={{ background: '#000', borderRadius: 16, padding: '1.35rem', border: '1px solid rgba(255,255,255,0.12)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
                <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#2563eb', color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem' }}>MK</div>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.85rem', color: '#fff' }}>Marta Kowalski <span style={{ color: '#38bdf8' }}>●</span></div>
                  <div style={{ fontSize: '0.72rem', color: '#71717a' }}>@martabuilds · 2h</div>
                </div>
              </div>
              <p style={{ fontSize: '0.82rem', color: '#e4e4e7', lineHeight: 1.5, margin: '0 0 1rem', whiteSpace: 'pre-wrap' }}>
                shipped writing styles today.{"\n\n"}the bug that almost stopped me: a render race that only appeared with 2+ tabs open. 3 hours, 1 line fix.{"\n\n"}it's always one line.
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#71717a', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '0.6rem' }}>
                <span>💬 12</span><span>🔁 48</span><span>❤️ 310</span><span>📊 21K</span>
              </div>
            </div>

            {/* LinkedIn Card */}
            <div style={{ background: '#fff', color: '#18181b', borderRadius: 16, padding: '1.35rem', border: '1px solid rgba(255,255,255,0.12)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
                <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#0a66c2', color: '#fff', fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem' }}>MK</div>
                <div>
                  <div style={{ fontWeight: 800, fontSize: '0.85rem', color: '#000' }}>Marta Kowalski · 1st</div>
                  <div style={{ fontSize: '0.72rem', color: '#64748b' }}>Founder at BuildLog · now · 🌐</div>
                </div>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#1e293b', lineHeight: 1.5, margin: '0 0 1rem', whiteSpace: 'pre-wrap' }}>
                Three weeks on workspace auth. Four people used it.{"\n\n"}Then I shipped autosave in an afternoon — 40 lines — and it's the change people actually thank me for.{"\n\n"}Build the boring thing that works.
              </p>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#64748b', borderTop: '1px solid #e2e8f0', paddingTop: '0.6rem' }}>
                <span>👍❤️💡 47 reactions</span><span>6 comments</span>
              </div>
            </div>

            {/* Reddit Card */}
            <div style={{ background: '#1a1a1b', borderRadius: 16, padding: '1.35rem', border: '1px solid rgba(255,255,255,0.12)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.6rem' }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#ff4500', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem' }}>🤖</div>
                <span style={{ fontWeight: 800, fontSize: '0.8rem', color: '#fff' }}>r/SideProject</span>
                <span style={{ fontSize: '0.7rem', color: '#71717a' }}>· 5h</span>
              </div>
              <h4 style={{ fontSize: '0.88rem', fontWeight: 800, color: '#fff', margin: '0 0 0.5rem', lineHeight: 1.35 }}>
                Spent 3 hours on a bug that was one line. Every time.
              </h4>
              <p style={{ fontSize: '0.78rem', color: '#d4d4d8', lineHeight: 1.45, margin: '0 0 1rem' }}>
                Render race that only showed up with 2+ tabs open. Logs looked fine. The fix was one line — it's always one line. Curious how others track these down...
              </p>
              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.72rem', color: '#a1a1aa', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '0.6rem' }}>
                <span>🔺 248</span><span>💬 32</span><span>🔗 Share</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <InlineCTA
        line="All three engines are on the free plan. See what it writes for your business."
        onStart={() => navigate('/auth')}
      />

      {/* WHAT ELSE IS IN THERE.
          Six capabilities that shipped and were never sold. A visitor about to
          see a price is weighing whether $17 covers a toy or a tool, and every
          one of these is the difference -- control over WHEN it posts, a way to
          stop it without losing anything, and a human to ask when it breaks.
          Placed above the price because that is the question the price is
          answering. Every item here is a feature that exists in the schema;
          nothing on this list is aspirational. */}
      <section>
        <div className="wrap">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <span className="eyebrow">Included on every plan</span>
            <h2 className="h2" style={{ margin: '1.1rem auto .9rem', maxWidth: 720 }}>
              The parts nobody advertises, that decide whether you keep using it
            </h2>
            <p className="lede" style={{ maxWidth: 620, margin: '0 auto' }}>
              Generating content is the easy half. These are the things that make
              running it for six months survivable.
            </p>
          </div>

          <div className="grid g3">
            {[
              [<Clock size={17} />, 'You choose the hours it posts',
               'Pick the days and the time range, in your own timezone. A fixed interval drifts through the clock and starts posting at 3am; this does not.'],
              [<Eye size={17} />, 'Nothing publishes unreviewed',
               'Every post can sit as a draft until you approve it. Turn that off once you trust it, per business.'],
              [<AlertCircle size={17} />, 'Pause without losing anything',
               'Hold a business during a rebrand or a holiday. Your accounts stay connected, your catalog stays put, and nothing goes out.'],
              [<Building2 size={17} />, 'Run more than one brand',
               'Separate workspaces, each with its own voice, schedule, catalog and connected accounts. Add teammates to the ones they should see.'],
              [<ShieldCheck size={17} />, 'Your accounts, your tokens',
               'Connected through official Facebook and Instagram login. Revoke it from Meta at any time and posting simply stops.'],
              [<Send size={17} />, 'A person answers you',
               'Report a problem in the app and the reply lands on the same screen, with a status you can watch change. Not a ticket address that goes quiet.'],
            ].map(([icon, title, body]) => (
              <div key={title} className="glass" style={{ padding: '1.6rem' }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10,
                  background: 'rgba(109,40,217,0.09)', border: '1px solid rgba(109,40,217,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'var(--violet)', marginBottom: '1rem',
                }}>{icon}</div>
                <h3 style={{ fontSize: '1.02rem', marginBottom: '.55rem', fontWeight: 690 }}>{title}</h3>
                <p style={{ fontSize: '.88rem', lineHeight: 1.65 }}>{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      {/* Renders nothing until a review has been approved. Placed immediately
          above the price, because proof is what a price gets read against. */}
      <ReviewWall />

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
            {plans.filter(p => !p.custom).map(p => {
              // Enterprise is quoted, not listed. Without this it rendered at
              // $0 as "Free" — reading as the cheapest tier, not the dearest.
              const custom = !!p.custom;
              const free = !custom && p.price <= 0;
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
                    {custom ? 'Custom' : free ? 'Free' : <>
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

                  <button className={`b ${hero ? 'b-primary' : 'b-ghost'}`} style={{ width: '100%' }}
                    onClick={() => custom
                      ? (window.location.href = 'mailto:vinayaksilswal@gmail.com?subject=Enterprise%20plan%20enquiry')
                      : navigate('/auth')}>
                    {custom ? (p.cta || 'Contact us') : free ? 'Start free' : `Choose ${p.name}`}
                  </button>
                </div>
              );
            })}
          </div>

          {/* A quoted tier as the fifth card left a lonely half-width box on
              desktop. A full-width band reads as deliberate, and is the
              conventional place buyers look for "call us" pricing. */}
          {plans.filter(p => p.custom).map(p => (
            <div key={p.code} className="glass" style={{
              marginTop: '1.1rem', padding: '1.6rem 1.8rem', display: 'flex',
              flexWrap: 'wrap', alignItems: 'center', gap: '1.2rem',
              justifyContent: 'space-between',
            }}>
              <div style={{ minWidth: 220 }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>{p.name}</h3>
                <div style={{ fontSize: '1.6rem', fontWeight: 780, lineHeight: 1.2, margin: '.25rem 0' }}>Custom</div>
                <p style={{ fontSize: '.85rem', margin: 0 }}>{p.tagline}</p>
              </div>
              <ul style={{
                listStyle: 'none', padding: 0, margin: 0, flex: '1 1 320px',
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '.5rem',
              }}>
                {p.features.map(f => (
                  <li key={f} style={{ display: 'flex', gap: '.5rem', fontSize: '.85rem' }}>
                    <CheckCircle2 size={15} color="var(--green)" style={{ flexShrink: 0, marginTop: 2 }} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <button className="b b-ghost" style={{ whiteSpace: 'nowrap' }}
                onClick={() => (window.location.href = 'mailto:vinayaksilswal@gmail.com?subject=Enterprise%20plan%20enquiry')}>
                {p.cta || 'Contact us'}
              </button>
            </div>
          ))}

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
            <Logo size={40} showWordmark />
          </div>
          <div style={{ display: 'flex', gap: '1.4rem', fontSize: '.85rem' }}>
            <a href="/privacy" style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>Privacy</a>
            <a href="/terms" style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>Terms</a>
            <a href="/dpa" style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>DPA</a>
          </div>
          <span style={{ fontSize: '.82rem', color: 'var(--ink-faint)' }}>
            © {new Date().getFullYear()} Organiflo
          </span>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
