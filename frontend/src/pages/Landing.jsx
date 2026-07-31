import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle2, TrendingUp, Sparkles, Zap, PlayCircle, Users, 
  ShieldCheck, ChevronDown, ArrowRight,
  BarChart3, Link, Target, Clock, Bot, Eye, DollarSign,
  Layers, Cpu, Globe, Lock, RefreshCw, Frown, AlertCircle, ThumbsUp, XCircle, LayoutDashboard,
  Instagram, Facebook, Linkedin, Twitter, Film, Image as ImageIcon, Send, CheckCheck, Building2
} from 'lucide-react';
import { Helmet } from 'react-helmet-async';

import { API_BASE } from '../config';
const PUBLIC_API = API_BASE.replace('/api/v1', '');

const premiumStyles = `
  .hero-gradient {
    background: radial-gradient(circle at top right, rgba(139, 92, 246, 0.15), transparent 40%),
                radial-gradient(circle at bottom left, rgba(59, 130, 246, 0.15), transparent 40%);
  }
  .glass-card {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
  }
  .premium-text-gradient {
    background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .accent-gradient {
    background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .interactive-hover:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(139, 92, 246, 0.15);
    border-color: rgba(139, 92, 246, 0.3);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .spin-slow {
    animation: spin 3s linear infinite;
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;

const Landing = () => {
  const navigate = useNavigate();
  const [activeFaq, setActiveFaq] = useState(null);
  const [liveStats, setLiveStats] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  
  // ROI Calculator state
  const [hourlyRate, setHourlyRate] = useState(50);
  const [hoursPerWeek, setHoursPerWeek] = useState(10);

  // Demo Generator state
  const [demoBizName, setDemoBizName] = useState('');
  const [demoBizModel, setDemoBizModel] = useState('SaaS');
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoPreview, setDemoPreview] = useState(null);

  // Self promotion data
  const [selfPromoData, setSelfPromoData] = useState(null);

  // The plan catalogue comes from the billing service, never from hardcoded
  // markup. Prices and limits shown here are then always what is actually
  // charged and enforced — a landing page that drifts from the biller is how
  // customers end up buying something they do not receive.
  //
  // The fallback mirrors services/billing_service.PLANS. It exists because a
  // pricing section that renders a spinner when the API is unreachable sells
  // nothing at all — the one part of this page that must never fail to draw is
  // the price. Keep the two in step when plans change.
  const FALLBACK_PLANS = [
    { code: 'free', name: 'Free', price: 0, tagline: 'Try the whole pipeline before you pay.',
      features: ['1 business', '5 published posts a month', '3 AI creative prompts a month', 'Facebook + Instagram publishing'] },
    { code: 'starter', name: 'Starter', price: 17, tagline: 'One business, running itself.',
      features: ['1 business', '60 published posts a month', '30 AI creative prompts a month', '1,000 marketing emails a month', 'Automated posting every 2 hours'] },
    { code: 'growth', name: 'Growth', price: 49, tagline: 'Several brands, one operator.',
      features: ['5 businesses', '300 published posts a month', '150 AI creative prompts a month', '10,000 marketing emails a month', 'Your own email sending domain'] },
    { code: 'agency', name: 'Agency', price: 149, tagline: 'Run marketing for clients.',
      features: ['25 businesses', 'Unlimited published posts', '600 AI creative prompts a month', '50,000 marketing emails a month', 'Team seats and roles'] },
  ];

  const [plans, setPlans] = useState(FALLBACK_PLANS);

  useEffect(() => {
    fetch(`${API_BASE}/billing/plans`)
      .then(r => r.json())
      .then(d => { if (Array.isArray(d?.plans) && d.plans.length) setPlans(d.plans); })
      .catch(() => { /* the fallback above is already showing */ });
  }, []);

  const paidPlans = plans.filter(p => p.price > 0);
  const freePlan = plans.find(p => p.price <= 0);
  const entryPrice = paidPlans.length ? Math.min(...paidPlans.map(p => p.price)) : 17;

  // Fetch live platform stats & self promotion data
  useEffect(() => {
    fetch(`${PUBLIC_API}/api/public/stats`)
      .then(r => r.json())
      .then(data => setLiveStats(data))
      .catch(() => {});

    fetch(`${PUBLIC_API}/api/public/recent-activity`)
      .then(r => r.json())
      .then(data => { if (data?.data) setRecentActivity(data.data); })
      .catch(() => {});

    fetch(`${PUBLIC_API}/api/public/self-promotion`)
      .then(r => r.json())
      .then(data => { if (data) setSelfPromoData(data); })
      .catch(() => {});
  }, []);

  const scrollToPricing = () => {
    document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleFaq = (index) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  const monthlySavings = ((hoursPerWeek * 4) * hourlyRate) - entryPrice;
  const yearlySavings = monthlySavings * 12;

  const faqs = [
    {
      question: "Do I need technical skills to use OrganicAI?",
      answer: "Not at all. We built OrganicAI to be as simple as connecting your social accounts and telling us your target audience. Our AI handles the generation, scheduling, and posting automatically."
    },
    {
      question: "Can I review the content before it's posted?",
      answer: "Yes! While you can put it on full autopilot with auto-approve, we also offer a review queue where you can approve, edit, or reject AI-generated drafts before they go live."
    },
    {
      question: "Which platforms do you currently support?",
      // Meta is the only one-click flow. X and LinkedIn publish, but you must
      // supply your own API token — saying "direct integration" for all four
      // would be selling a connect button that does not exist.
      answer: "Facebook and Instagram connect in one click through Meta — that is the flow we support end to end, including Reels. X (Twitter) and LinkedIn can publish too, but you supply your own API token for those rather than clicking Connect."
    },
    {
      question: "Is there a long-term contract?",
      answer: "No. Our pricing is month-to-month. Cancel anytime from your dashboard with two clicks — no questions asked, no hidden fees."
    },
    {
      question: "How does the AI understand my brand voice?",
      answer: "When you onboard, our AI analyzes your business description, website, and target audience to build a Brand Context Profile. It identifies your tone of voice, content pillars, and generates relevant hashtags. Every post is tailored to your brand, not generic templates."
    },
    {
      question: "What happens after I sign up?",
      answer: "After registration, you'll describe your business. Our AI immediately analyzes your brand and auto-generates starter creatives — posts ready to publish with AI-generated images. Your media library is pre-populated so you can start automating within minutes."
    }
  ];

  return (
    <div className="view hero-gradient" style={{ minHeight: '100vh' }}>
      <style>{premiumStyles}</style>
      <Helmet>
        <title>OrganicAI — The Autonomous Marketing Employee</title>
        <meta name="description" content="AI writes brand-matched social posts and publishes them to Facebook and Instagram on autopilot. Free plan, no card required." />
        <meta name="keywords" content="AI marketing, social media automation, organic growth, content generation, automated posting" />
        <script type="application/ld+json">{JSON.stringify({
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          "name": "OrganicAI",
          "applicationCategory": "BusinessApplication",
          "offers": { "@type": "Offer", "price": "17", "priceCurrency": "USD" },
          "description": "AI-powered organic marketing automation platform"
        })}</script>
      </Helmet>
      
      {/* Navbar */}
      <nav className="navbar" style={{ background: 'rgba(9, 9, 11, 0.8)', backdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', padding: '0.5rem 0' }}>
          <div className="nav-brand" style={{ cursor: 'pointer' }} onClick={() => window.scrollTo(0,0)}>
            <Sparkles size={24} color="#a855f7" />
            <span style={{ fontWeight: 700, letterSpacing: '-0.02em', fontSize: '1.25rem' }}>OrganicAI</span>
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <button className="btn btn-secondary" style={{ border: 'none', background: 'transparent' }} onClick={() => navigate('/auth')}>Log in</button>
            <button className="btn btn-primary" style={{ boxShadow: '0 4px 14px rgba(168, 85, 247, 0.4)' }} onClick={() => navigate('/auth')}>Start free</button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero" style={{ paddingTop: '8rem', paddingBottom: '4rem', textAlign: 'center' }}>
        <div className="container">
          <div className="hero-content" style={{ margin: '0 auto' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(168, 85, 247, 0.1)', border: '1px solid rgba(168, 85, 247, 0.2)', padding: '0.5rem 1rem', borderRadius: '999px', marginBottom: '2rem', color: '#c084fc', fontWeight: '600', fontSize: '0.875rem' }}>
              <Cpu size={16} /> Fully Autonomous Marketing Engine
            </div>
            <h1 className="premium-text-gradient" style={{ fontSize: '4.5rem', fontWeight: 800, lineHeight: 1.1, letterSpacing: '-0.03em', marginBottom: '1.5rem' }}>
              Scale Your Audience<br />on <span className="accent-gradient">Autopilot</span>.
            </h1>
            <p style={{ fontSize: '1.25rem', maxWidth: '700px', margin: '0 auto 2.5rem', color: '#a1a1aa', lineHeight: 1.6 }}>
              An AI marketing employee that learns your brand, writes the copy and the
              creative brief, and publishes it to your <strong>Facebook Page and Instagram</strong> on
              the schedule you set.
            </p>
            <div className="hero-cta" style={{ display: 'flex', gap: '1rem', justifyContent: 'center', margin: '2rem auto 1rem', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <button className="btn btn-primary btn-large pulse" onClick={() => navigate('/auth')} style={{ fontSize: '1.1rem', padding: '1rem 2rem', boxShadow: '0 8px 24px rgba(168, 85, 247, 0.4)' }}>
                  Start free — no card <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
                </button>
                <button className="btn btn-secondary btn-large glass-card" onClick={scrollToPricing} style={{ fontSize: '1.1rem', padding: '1rem 2rem', color: '#fff' }}>
                  See How It Works
                </button>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#71717a', marginTop: '0.5rem' }}>
                {/* Was "14-Day Money-Back Guarantee" — a refund promise with no
                    refund process behind it. The free plan is a stronger offer
                    anyway: there is nothing to get back. Put the guarantee back
                    if you decide to honour one. */}
                <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '0.25rem', color: '#10b981' }} /> Free plan, no card. Cancel any time.
              </p>
            </div>
            <div style={{ marginTop: '2rem', color: '#71717a', fontSize: '0.875rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '2rem', flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981"/> Set & Forget</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981"/> High Converting Copy</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981"/> AI Creatives Instantly</span>
            </div>
          </div>
          
          {/* Dashboard Mockup */}
          <div className="mockup-container">
            <div className="mockup-header">
              <div className="mockup-dot" style={{ background: '#ef4444' }}></div>
              <div className="mockup-dot" style={{ background: '#f59e0b' }}></div>
              <div className="mockup-dot" style={{ background: '#10b981' }}></div>
            </div>
            <div className="mockup-body" style={{ height: '400px' }}>
              <div className="mockup-sidebar">
                <div style={{ width: '100%', height: '24px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', marginBottom: '1.5rem' }}></div>
                <div style={{ width: '80%', height: '16px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '1rem' }}></div>
                <div style={{ width: '90%', height: '16px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '1rem' }}></div>
                <div style={{ width: '70%', height: '16px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', marginBottom: '1rem' }}></div>
              </div>
              <div className="mockup-content" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <LayoutDashboard size={20} color="var(--primary-color)" />
                    <span style={{ fontWeight: 600, fontSize: '1.1rem' }}>Active Campaign: Social Growth</span>
                  </div>
                  <span className="badge active"><RefreshCw size={12} className="spin-slow" style={{ marginRight: '0.25rem' }} /> Auto-Publishing ON</span>
                </div>
                
                <div style={{ display: 'flex', gap: '1rem', flex: 1 }}>
                  {/* Simulated Image Gen */}
                  <div style={{ flex: 1, background: 'rgba(0,0,0,0.4)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'linear-gradient(45deg, rgba(168,85,247,0.1), rgba(59,130,246,0.1))', animation: 'pulseGlow 4s infinite alternate' }}></div>
                    <div style={{ textAlign: 'center', zIndex: 1 }}>
                       <Sparkles size={32} color="var(--primary-color)" style={{ marginBottom: '1rem', animation: 'float 3s infinite' }} />
                       <p style={{ fontSize: '0.85rem', color: 'var(--primary-color)', fontWeight: 600 }}>Generating Visuals...</p>
                    </div>
                  </div>
                  {/* Simulated Copy Gen */}
                  <div style={{ flex: 1.5, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                       <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}><Bot size={14} color="#a1a1aa" /> <span style={{ fontSize: '0.75rem', color: '#a1a1aa' }}>Analyzing brand voice...</span></div>
                       <div className="skeleton-card" style={{ height: '8px', width: '80%', borderRadius: '4px', marginBottom: '0.5rem' }}></div>
                       <div className="skeleton-card" style={{ height: '8px', width: '100%', borderRadius: '4px', marginBottom: '0.5rem' }}></div>
                       <div className="skeleton-card" style={{ height: '8px', width: '60%', borderRadius: '4px' }}></div>
                    </div>
                    <div style={{ padding: '1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#a1a1aa', marginBottom: '0.5rem' }}>
                        <span>Target Platforms</span>
                        <span style={{ color: 'var(--success)' }}>Ready</span>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                         <div style={{ padding: '0.25rem 0.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', fontSize: '0.7rem' }}>Instagram</div>
                         <div style={{ padding: '0.25rem 0.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', fontSize: '0.7rem' }}>LinkedIn</div>
                         <div style={{ padding: '0.25rem 0.5rem', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', fontSize: '0.7rem' }}>X (Twitter)</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Real integrations — the platforms we actually publish to */}
      <div className="integration-bar">
        <div className="container">
          {/* Meta is one click; X and LinkedIn need the customer's own API
              token. Listing all four as equals promised a connect button that
              does not exist for two of them. */}
          <p className="integration-bar-label">One-click publishing to Facebook and Instagram · X and LinkedIn with your own API token</p>
          <div className="integration-logos">
            {[
              { name: 'Instagram', icon: <Instagram size={22} />, color: '#e1306c' },
              { name: 'Facebook', icon: <Facebook size={22} />, color: '#1877f2' },
              { name: 'LinkedIn', icon: <Linkedin size={22} />, color: '#0a66c2' },
              { name: 'X (Twitter)', icon: <Twitter size={22} />, color: '#e5e7eb' },
            ].map(p => (
              <div key={p.name} className="integration-chip">
                <span style={{ color: p.color, display: 'flex' }}>{p.icon}</span>
                <span>{p.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* How It Works — the real product flow */}
      <section style={{ padding: '6rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3.5rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em', fontSize: '0.85rem', margin: 0 }}>How it works</h4>
            <h2 style={{ fontSize: '2.5rem', margin: '0.75rem auto 1rem', maxWidth: '720px' }}>Add your business once. It markets itself from then on.</h2>
            <p style={{ color: '#a1a1aa', maxWidth: '580px', margin: '0 auto', fontSize: '1.05rem' }}>
              Four steps. No calendars to fill, no briefs to write, no designer to brief.
            </p>
          </div>

          <div className="how-steps">
            {[
              {
                n: '01', icon: <Building2 size={20} />, title: 'Add your business',
                body: 'Drop in your website and a short description. The AI reads your site and builds a brand profile — tone, audience, content pillars, colours.',
                visual: (
                  <div className="hiw-visual">
                    <div className="hiw-field"><span className="hiw-label">Website</span><span className="hiw-value">yourbrand.com</span></div>
                    <div className="hiw-field"><span className="hiw-label">Model</span><span className="hiw-chip">E-commerce</span></div>
                    <div className="hiw-analysing"><Bot size={13} /> Analysing brand voice…</div>
                  </div>
                )
              },
              {
                n: '02', icon: <Film size={20} />, title: 'AI writes the prompt & creative',
                body: 'It generates a full cinematic video prompt and on-brand visuals — and shows you the exact prompt it used, so nothing is a black box.',
                visual: (
                  <div className="hiw-visual">
                    <div className="hiw-prompt">“Slow orbital dolly on the product, warm golden-hour rim light, matte ceramic finish…”</div>
                    <div className="hiw-thumbs">
                      <span /><span /><span />
                    </div>
                  </div>
                )
              },
              {
                n: '03', icon: <ImageIcon size={20} />, title: 'Lands in your media library',
                body: 'Every generated asset and its prompt is saved to that business’s own catalog. Reuse it, edit it, or let the scheduler pick it up.',
                visual: (
                  <div className="hiw-visual">
                    <div className="hiw-grid"><span /><span /><span /><span /><span /><span /></div>
                  </div>
                )
              },
              {
                n: '04', icon: <Send size={20} />, title: 'Review, then it publishes',
                body: 'Posts queue up in a review log. Approve them yourself, or switch on auto-approve and it publishes on your schedule — every 2 hours by default.',
                visual: (
                  <div className="hiw-visual">
                    <div className="hiw-row"><CheckCheck size={13} color="#10b981" /> Posted to Instagram <span className="hiw-time">2h ago</span></div>
                    <div className="hiw-row"><CheckCheck size={13} color="#10b981" /> Posted to LinkedIn <span className="hiw-time">4h ago</span></div>
                    <div className="hiw-row hiw-row-pending"><Clock size={13} color="#f59e0b" /> Queued — Facebook <span className="hiw-time">in 1h</span></div>
                  </div>
                )
              },
            ].map(s => (
              <div key={s.n} className="how-step glass-card">
                <div className="how-step-head">
                  <span className="how-step-num">{s.n}</span>
                  <span className="how-step-icon">{s.icon}</span>
                </div>
                <h3 style={{ fontSize: '1.15rem', margin: '0 0 0.5rem' }}>{s.title}</h3>
                <p style={{ fontSize: '0.92rem', color: '#a1a1aa', lineHeight: 1.6, margin: '0 0 1.25rem' }}>{s.body}</p>
                {s.visual}
              </div>
            ))}
          </div>

          <div style={{ textAlign: 'center', marginTop: '3rem' }}>
            <button className="btn btn-primary" onClick={() => navigate('/auth')} style={{ fontSize: '1.05rem', padding: '0.9rem 2rem' }}>
              Start free — no card <ArrowRight size={17} style={{ marginLeft: '0.5rem' }} />
            </button>
            <p style={{ fontSize: '0.85rem', color: '#71717a', marginTop: '0.85rem' }}>Cancel anytime · No contract · Secure PayPal checkout</p>
          </div>
        </div>
      </section>

      {/* Problem - Agitation - Solution (PAS) */}
      <section style={{ padding: '6rem 0', background: 'rgba(255,255,255,0.01)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <h4 style={{ color: '#ef4444', textTransform: 'uppercase', letterSpacing: '0.1em' }}>The Old Way</h4>
            <h2 style={{ fontSize: '2.5rem', maxWidth: '700px', margin: '0.5rem auto' }}>Manual marketing is draining your resources.</h2>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem', marginBottom: '4rem' }}>
            <div className="pas-card">
              <Frown size={40} color="#ef4444" style={{ marginBottom: '1.5rem' }} />
              <h3 style={{ fontSize: '1.25rem' }}>Creative Burnout</h3>
              <p style={{ fontSize: '1rem' }}>Staring at a blank screen trying to figure out what to post today. Wasting hours in Canva designing basic templates.</p>
            </div>
            <div className="pas-card">
              <XCircle size={40} color="#ef4444" style={{ marginBottom: '1.5rem' }} />
              <h3 style={{ fontSize: '1.25rem' }}>Inconsistent Posting</h3>
              <p style={{ fontSize: '1rem' }}>You get busy closing deals and forget to post for a week. The algorithm punishes you, and your reach drops to zero.</p>
            </div>
            <div className="pas-card">
              <AlertCircle size={40} color="#ef4444" style={{ marginBottom: '1.5rem' }} />
              <h3 style={{ fontSize: '1.25rem' }}>Expensive Agencies</h3>
              <p style={{ fontSize: '1rem' }}>Paying a freelancer or agency $2,000+/month just to schedule generic posts that don't sound like your brand.</p>
            </div>
          </div>

          <div className="glass-card" style={{ padding: '3rem', borderRadius: '24px', textAlign: 'center', background: 'linear-gradient(135deg, rgba(168,85,247,0.1), rgba(59,130,246,0.1))', border: '1px solid rgba(168,85,247,0.3)' }}>
             <h4 style={{ color: 'var(--success)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '1rem' }}>The New Way</h4>
             <h2 style={{ fontSize: '2.5rem', marginBottom: '1.5rem' }}>Meet your autonomous AI Marketing Team.</h2>
             <p style={{ fontSize: '1.1rem', maxWidth: '600px', margin: '0 auto 2rem' }}>OrganicAI doesn't just schedule. It <strong>generates, designs, and publishes</strong> contextually relevant content 24/7. Never miss a post again.</p>
             <button className="btn btn-primary" onClick={() => navigate('/auth')} style={{ fontSize: '1.1rem', padding: '1rem 2rem' }}>Experience the Solution <ArrowRight size={18} style={{ marginLeft: '0.5rem' }} /></button>
          </div>
        </div>
      </section>

      {/* Live Stats Ticker — Real Data */}
      <section className="social-proof-section">
        <div className="ticker-wrap">
          <div className="ticker-content">
            <div className="ticker-item">
              <span className="ticker-value">{liveStats?.posts || '—'}</span>
              <span className="ticker-label">Posts Generated (Live)</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">1-click</span>
              <span className="ticker-label">Facebook + Instagram</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">&lt;2 min</span>
              <span className="ticker-label">Setup Time</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">${entryPrice}</span>
              <span className="ticker-label">Starts At</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">{liveStats?.users || '—'}</span>
              <span className="ticker-label">Active Users (Live)</span>
            </div>
            {/* Duplicates for seamless looping */}
            <div className="ticker-item">
              <span className="ticker-value">{liveStats?.posts || '—'}</span>
              <span className="ticker-label">Posts Generated (Live)</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">1-click</span>
              <span className="ticker-label">Facebook + Instagram</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">&lt;2 min</span>
              <span className="ticker-label">Setup Time</span>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works / Demo */}
      <section style={{ padding: '6rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <h2 style={{ fontSize: '2.5rem', fontWeight: 700 }}>Try the Context Engine</h2>
            <p style={{ color: '#a1a1aa', marginTop: '1rem' }}>See what our AI can generate for your brand in 5 seconds.</p>
          </div>

          <div className="glass-card" style={{ maxWidth: '800px', margin: '0 auto', padding: '3rem', borderRadius: '24px' }}>
            <form onSubmit={(e) => {
              e.preventDefault();
              if (!demoBizName.trim()) return;
              setDemoLoading(true);
              setTimeout(() => {
                const encoded = encodeURIComponent(`Professional highly engaging social media post visual for ${demoBizName}, ${demoBizModel} industry, high quality, cinematic lighting, ultra detailed`);
                setDemoPreview({
                  caption: `🚀 Big things are happening at ${demoBizName}! We're leveraging cutting-edge automation to scale our ${demoBizModel} operations faster than ever. When you eliminate manual work, you make room for real innovation. What's the biggest bottleneck in your business right now? Drop a comment below! 👇\n\n#${demoBizName.replace(/\s+/g, '')} #Innovation #Scale #BusinessGrowth`,
                  imageUrl: `https://image.pollinations.ai/prompt/${encoded}?width=1080&height=1080&nologo=true`,
                  topic: 'Brand Growth & Spotlight'
                });
                setDemoLoading(false);
              }, 1200);
            }} style={{ display: 'grid', gridTemplateColumns: '1fr 180px 140px', gap: '1rem', marginBottom: '2rem' }}>
              <input type="text" placeholder="Your Business Name..." value={demoBizName} onChange={e => setDemoBizName(e.target.value)} required style={{ padding: '1rem 1.25rem', borderRadius: '12px', background: 'rgba(0,0,0,0.5)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }} />
              <select value={demoBizModel} onChange={e => setDemoBizModel(e.target.value)} style={{ padding: '1rem', borderRadius: '12px', background: 'rgba(0,0,0,0.5)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' }}>
                <option value="SaaS">SaaS / Tech</option>
                <option value="E-commerce">E-Commerce</option>
                <option value="Agency">Agency</option>
                <option value="Local Business">Local Business</option>
              </select>
              <button type="submit" className="btn btn-primary" disabled={demoLoading} style={{ borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {demoLoading ? <span className="spinner"></span> : <><Sparkles size={16} style={{marginRight: '0.5rem'}}/> Generate</>}
              </button>
            </form>

            {demoPreview && (
              <div className="fade-in glass-card" style={{ borderRadius: '16px', overflow: 'hidden', display: 'grid', gridTemplateColumns: '300px 1fr', border: '1px solid rgba(168,85,247,0.3)' }}>
                <div style={{ width: '100%', height: '300px', background: '#000' }}>
                  <img src={demoPreview.imageUrl} alt="AI Visual" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
                <div style={{ padding: '2rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', background: 'rgba(0,0,0,0.4)' }}>
                  <div>
                    <span style={{ display: 'inline-block', background: 'rgba(168,85,247,0.15)', color: '#c084fc', padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, marginBottom: '1rem' }}>
                      ⚡ Generated Topic: {demoPreview.topic}
                    </span>
                    <p style={{ fontSize: '1rem', lineHeight: 1.6, color: '#e4e4e7', margin: 0 }}>{demoPreview.caption}</p>
                  </div>
                  <button className="btn btn-primary" style={{ width: 'fit-content', marginTop: '1.5rem' }} onClick={() => navigate('/auth')}>
                    Automate This Flow <ArrowRight size={16} style={{marginLeft: '0.5rem'}}/>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* What Makes This Different — Genuine Value Props */}
      <section style={{ padding: '5rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Built Different</h4>
            <h2>Stop Scheduling. Start Automating.</h2>
            <p style={{ maxWidth: '640px', margin: '0.5rem auto 0', fontSize: '1.05rem' }}>Most tools just schedule what <strong>you</strong> write. OrganicAI acts as your autonomous marketing employee—handling the ideation, creation, and distribution end-to-end.</p>
          </div>

          <div className="hero-stats">
            <div className="stat-card">
              <div className="stat-card-icon"><Cpu size={32} /></div>
              <h3>Brand Context Engine</h3>
              <p>AI analyzes your business to understand your voice, audience, and niche. Every post sounds like you, not a robot. It learns your brand's DNA.</p>
            </div>
            <div className="stat-card">
              <div className="stat-card-icon"><Eye size={32} /></div>
              <h3>AI-Generated Visuals</h3>
              <p>Each post comes with a custom AI-generated image. No stock photos, no Canva templates. Unique, on-brand visuals generated for every piece of content.</p>
            </div>
            <div className="stat-card">
              <div className="stat-card-icon"><Clock size={32} /></div>
              <h3>True Autopilot</h3>
              <p>Set your schedule (2hr, 4hr, 8hr, or custom intervals) and turn on auto-approve. Content is generated and published without you lifting a finger.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Self-Promotion AI Engine Live Showcase */}
      <section style={{ padding: '6rem 0', background: 'rgba(0,0,0,0.3)', borderTop: '1px solid rgba(255,255,255,0.05)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.4rem 1rem', borderRadius: '999px', color: '#10b981', fontWeight: '600', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
              <RefreshCw size={14} className="spin-slow" /> Self-Marketing AI Engine: ACTIVE
            </div>
            <h2 style={{ fontSize: '2.5rem', fontWeight: 700, marginBottom: '1rem' }}>We use OrganicAI to grow OrganicAI.</h2>
            <p style={{ maxWidth: '640px', margin: '0 auto', color: '#a1a1aa', fontSize: '1.1rem' }}>
              Our platform operates autonomously on a 2-hour interval, generating creatives and publishing them to promote this very service. Below are its latest live creations:
            </p>
          </div>

          {selfPromoData?.campaigns?.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '2rem' }}>
              {selfPromoData.campaigns.slice(0, 3).map((item, idx) => (
                <div key={idx} className="glass-card interactive-hover" style={{ borderRadius: '20px', overflow: 'hidden', transition: 'all 0.3s ease' }}>
                  <div style={{ height: '240px', background: '#000', position: 'relative' }}>
                    <img src={item.mediaUrl} alt="AI Promo" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.9 }} />
                    <div style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', padding: '0.25rem 0.75rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600, color: '#c084fc' }}>
                      Auto-Generated
                    </div>
                  </div>
                  <div style={{ padding: '1.5rem' }}>
                    <p style={{ fontSize: '0.95rem', lineHeight: 1.6, color: '#e4e4e7', margin: 0 }}>{item.caption}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-card" style={{ textAlign: 'center', padding: '3rem', borderRadius: '20px', color: '#a1a1aa' }}>
              <RefreshCw size={32} className="spin-slow" style={{ margin: '0 auto 1rem', color: '#c084fc' }} />
              <p>Self-promotion engine is running its background cycle...</p>
            </div>
          )}
        </div>
      </section>

      {/* Use Cases */}
      <section style={{ padding: '4rem 0', background: 'rgba(255,255,255,0.01)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Use Cases</h4>
            <h2>Built for businesses that need to grow organically</h2>
          </div>
          <div className="hero-stats">
            <div className="stat-card">
              <div className="stat-card-icon"><Zap size={32} /></div>
              <h3>SaaS & B2B</h3>
              <p>Generate LinkedIn posts, Twitter threads, and thought leadership content that drives inbound leads and demo bookings on autopilot.</p>
            </div>
            <div className="stat-card">
              <div className="stat-card-icon"><PlayCircle size={32} /></div>
              <h3>E-Commerce</h3>
              <p>Sync your product catalog. AI creates product showcase posts, sale announcements, and lifestyle content with product images. Connect directly to your store.</p>
            </div>
            <div className="stat-card">
              <div className="stat-card-icon"><Users size={32} /></div>
              <h3>Creators & Agencies</h3>
              <p>Manage multiple brand workspaces from one account. Each workspace has its own brand context, content pillars, and posting schedule.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ROI Calculator */}
      <section id="roi" style={{ padding: '6rem 0', background: 'rgba(255,255,255,0.02)' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <h2 style={{ fontSize: '2.5rem', fontWeight: 700 }}>Calculate Your ROI</h2>
            <p style={{ color: '#a1a1aa', marginTop: '1rem' }}>See the true cost of manual marketing vs OrganicAI.</p>
          </div>

          <div className="glass-card" style={{ maxWidth: '800px', margin: '0 auto', padding: '3rem', borderRadius: '24px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '3rem' }}>
              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#a1a1aa', marginBottom: '0.5rem', fontSize: '0.9rem' }}><DollarSign size={16} /> Your Hourly Rate ($)</label>
                <input type="number" value={hourlyRate} onChange={e => setHourlyRate(Number(e.target.value) || 0)} min="1" style={{ width: '100%', padding: '1rem', borderRadius: '12px', background: 'rgba(0,0,0,0.5)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', fontSize: '1.25rem', fontWeight: 600 }} />
              </div>
              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#a1a1aa', marginBottom: '0.5rem', fontSize: '0.9rem' }}><Clock size={16} /> Hours/Week on Marketing</label>
                <input type="number" value={hoursPerWeek} onChange={e => setHoursPerWeek(Number(e.target.value) || 0)} min="1" style={{ width: '100%', padding: '1rem', borderRadius: '12px', background: 'rgba(0,0,0,0.5)', color: '#fff', border: '1px solid rgba(255,255,255,0.1)', fontSize: '1.25rem', fontWeight: 600 }} />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1.5rem', textAlign: 'center' }}>
              <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '2rem 1.5rem', borderRadius: '16px' }}>
                <p style={{ fontSize: '0.85rem', color: '#a1a1aa', margin: '0 0 0.5rem 0' }}>Manual Cost / Month</p>
                <p style={{ fontSize: '2.5rem', fontWeight: 800, color: '#ef4444', margin: 0 }}>${(hoursPerWeek * 4 * hourlyRate).toLocaleString()}</p>
              </div>
              <div style={{ background: 'rgba(168, 85, 247, 0.1)', border: '1px solid rgba(168, 85, 247, 0.3)', padding: '2rem 1.5rem', borderRadius: '16px', position: 'relative' }}>
                <div style={{ position: 'absolute', top: '-12px', left: '50%', transform: 'translateX(-50%)', background: '#a855f7', color: '#fff', padding: '0.2rem 0.8rem', borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700 }}>OUR PRICE</div>
                <p style={{ fontSize: '0.85rem', color: '#a1a1aa', margin: '0 0 0.5rem 0' }}>OrganicAI Cost</p>
                <p style={{ fontSize: '2.5rem', fontWeight: 800, color: '#c084fc', margin: 0 }}>${entryPrice}</p>
              </div>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '2rem 1.5rem', borderRadius: '16px' }}>
                <p style={{ fontSize: '0.85rem', color: '#a1a1aa', margin: '0 0 0.5rem 0' }}>You Save / Year</p>
                <p style={{ fontSize: '2.5rem', fontWeight: 800, color: '#10b981', margin: 0 }}>${Math.max(0, yearlySavings).toLocaleString()}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Live Activity Feed */}
      {recentActivity.length > 0 && (
        <section style={{ padding: '4rem 0', background: 'rgba(255,255,255,0.01)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
              <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Live Platform Activity</h4>
              <h2>Recent posts from the OrganicAI network</h2>
              <p style={{ maxWidth: '500px', margin: '0 auto' }}>Real content published by businesses using OrganicAI right now.</p>
            </div>
            <div style={{ maxWidth: '640px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {recentActivity.map((item, i) => (
                <div key={i} className="glass-panel" style={{ padding: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--primary-color)', textTransform: 'uppercase' }}>{item.platform}</span>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem' }}>{item.caption}</p>
                  </div>
                  {item.postedAt && (
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', marginLeft: '1rem' }}>
                      {new Date(item.postedAt).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Trust Signals */}
      <section style={{ padding: '4rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <h2>Built for trust, not lock-in</h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '2rem', maxWidth: '900px', margin: '0 auto' }}>
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <Lock size={36} color="var(--primary-color)" style={{ marginBottom: '1rem' }} />
              <h4>Your Data, Your Control</h4>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>We never sell or share your business data. Export everything anytime.</p>
            </div>
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <ShieldCheck size={36} color="var(--primary-color)" style={{ marginBottom: '1rem' }} />
              <h4>No Lock-in, Cancel Anytime</h4>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Month-to-month billing. Cancel with two clicks from your dashboard. We earn your business monthly.</p>
            </div>
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <Globe size={36} color="var(--primary-color)" style={{ marginBottom: '1rem' }} />
              <h4>Multi-Workspace Support</h4>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Manage multiple brands or clients from one account with isolated workspaces.</p>
            </div>
          </div>
        </div>
      </section>

      {/*
        This section previously held three invented testimonials — fictional
        people, fictional job titles, and fabricated results ("engagement is up
        300%"). Fake reviews on a page that takes payment are prohibited by the
        FTC and carry per-violation penalties, quite apart from what they do to
        a brand when a customer notices.

        Removing unverifiable praise costs nothing in conversion. What actually
        removes hesitation is telling people exactly what happens next, so that
        is what this section does now. Replace it with real testimonials the
        moment you have customers who will put their name to one.
      */}
      <section className="testimonials-section">
        <div className="container">
          <div style={{ textAlign: 'center' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>No guesswork</h4>
            <h2>Your first ten minutes</h2>
            <p style={{ maxWidth: '620px', margin: '0 auto' }}>
              Free to start, no card. Here is exactly what happens, in order.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginTop: '3rem' }}>
            {[
              {
                n: '01',
                t: 'Paste your website',
                b: 'We read it and build a brand profile — what you sell, who buys it, the words you use. About a minute.',
              },
              {
                n: '02',
                t: 'Connect Facebook & Instagram',
                b: 'One Meta login. Pick the Page and the Instagram account you want posts to land on.',
              },
              {
                n: '03',
                t: 'Review the first post',
                b: 'A caption written from your brand profile and the media you uploaded. Edit it, or approve it.',
              },
              {
                n: '04',
                t: 'Switch on auto-approve',
                b: 'From then on it publishes on your schedule. Every post stays in the log with its delivery result.',
              },
            ].map(s => (
              <div key={s.n} className="glass-card" style={{ padding: '1.75rem', borderRadius: 16 }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 800, color: 'var(--primary-color)', letterSpacing: '0.1em', marginBottom: '0.6rem' }}>
                  {s.n}
                </div>
                <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.05rem' }}>{s.t}</h3>
                <p style={{ margin: 0, fontSize: '0.88rem', lineHeight: 1.6, color: 'var(--text-muted)' }}>{s.b}</p>
              </div>
            ))}
          </div>

          <p style={{ textAlign: 'center', marginTop: '2.5rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            Nothing publishes until you allow it. Auto-approve is off by default.
          </p>
        </div>
      </section>

      {/* Pricing Section */}
      {/*
        Rendered from GET /billing/plans — the same catalogue the biller
        charges against and the quota checks enforce. The previous markup was
        hardcoded and claimed "no tiers, no hidden limits" and "unlimited brand
        workspaces", which stopped being true the moment metered plans shipped.
        Selling against copy the product does not honour is how refunds and
        chargebacks start.
      */}
      <section id="pricing" className="pricing-section">
        <div className="container">
          <div className="pricing-header">
            <h2>Start free. Pay when it earns its keep.</h2>
            <p style={{ maxWidth: '640px', margin: '0 auto', fontSize: '1.125rem' }}>
              Run the whole pipeline on the free plan first — no card. Upgrade when you
              want it posting every day.
            </p>
          </div>

          {plans.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem 0', color: 'var(--text-muted)' }}>
              <span className="spinner" style={{ width: 20, height: 20 }} />
            </div>
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '1.5rem',
              alignItems: 'stretch',
              maxWidth: 1150,
              margin: '0 auto',
            }}>
              {plans.map(p => {
                const isFree = p.price <= 0;
                const featured = p.code === 'starter';
                return (
                  <div key={p.code} className="glass-card" style={{
                    padding: '2rem 1.75rem',
                    borderRadius: 18,
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                    border: featured ? '1px solid var(--primary-color)' : '1px solid rgba(255,255,255,0.08)',
                    boxShadow: featured ? '0 0 40px rgba(168,85,247,0.18)' : undefined,
                  }}>
                    {featured && (
                      <div style={{
                        position: 'absolute', top: -12, left: '50%', transform: 'translateX(-50%)',
                        background: 'linear-gradient(135deg, #a855f7, #3b82f6)', color: '#fff',
                        padding: '0.2rem 0.85rem', borderRadius: 999, fontSize: '0.68rem', fontWeight: 800,
                        letterSpacing: '0.06em', whiteSpace: 'nowrap',
                      }}>
                        MOST POPULAR
                      </div>
                    )}

                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: featured ? 'var(--primary-color)' : undefined }}>
                      {p.name}
                    </h3>
                    <div style={{ margin: '0.7rem 0 0.2rem', fontSize: '2.4rem', fontWeight: 800, lineHeight: 1 }}>
                      {isFree ? 'Free' : <>
                        <span style={{ fontSize: '1.3rem', verticalAlign: 'super' }}>$</span>{p.price}
                        <span style={{ fontSize: '0.95rem', fontWeight: 400, color: 'var(--text-muted)' }}>/mo</span>
                      </>}
                    </div>
                    <p style={{ margin: '0.5rem 0 1.4rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.55, minHeight: 40 }}>
                      {p.tagline}
                    </p>

                    <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 1.75rem', display: 'grid', gap: '0.6rem', flex: 1 }}>
                      {p.features.map(f => (
                        <li key={f} style={{ display: 'flex', gap: '0.5rem', fontSize: '0.86rem', lineHeight: 1.5 }}>
                          <CheckCircle2 size={15} style={{ color: 'var(--success)', flexShrink: 0, marginTop: 2 }} />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>

                    <button
                      className={`btn ${featured ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => navigate('/auth')}
                      style={{ width: '100%', padding: '0.9rem', fontWeight: 700, fontSize: '0.95rem' }}
                    >
                      {isFree ? 'Start free' : `Choose ${p.name}`}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ textAlign: 'center', marginTop: '2.5rem', display: 'flex', flexDirection: 'column', gap: '0.6rem', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--success)', fontSize: '0.9rem' }}>
              <ShieldCheck size={16} /> Billed monthly through PayPal. Cancel any time from your dashboard.
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Cancelling keeps your access until the end of the period you have already paid for.
              We never see or store your card details.
            </span>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="faq-section">
        <div className="container">
          <div style={{ textAlign: 'center' }}>
            <h2>Frequently Asked Questions</h2>
            <p>Everything you need to know before getting started.</p>
          </div>
          
          <div className="faq-container">
            {faqs.map((faq, index) => (
              <div key={index} className={`faq-item ${activeFaq === index ? 'active' : ''}`}>
                <div className="faq-question" onClick={() => toggleFaq(index)}>
                  {faq.question}
                  <ChevronDown className="faq-icon" size={20} />
                </div>
                <div className="faq-answer">
                  {faq.answer}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
      
      {/* Bottom CTA */}
      <section className="bottom-cta">
        <div className="container" style={{ textAlign: 'center', padding: '4rem 0' }}>
          <h2 style={{ fontSize: '3rem', marginBottom: '1.5rem' }}>Ready to put your marketing on autopilot?</h2>
          <p style={{ fontSize: '1.25rem', maxWidth: '640px', margin: '0 auto 2.5rem', color: 'var(--text-main)' }}>
            Join the businesses saving hundreds of hours every month. Let OrganicAI handle the content, design, and scheduling so you can focus on closing deals.
          </p>
          <button className="btn btn-primary btn-large" onClick={() => navigate('/auth')} style={{ fontSize: '1.2rem', padding: '1.25rem 2.5rem' }}>
            Start free — no card <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ padding: '3rem 0', textAlign: 'center', background: 'var(--bg-dark)' }}>
        <div className="container">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Sparkles size={20} color="var(--primary-color)" />
            <span style={{ fontWeight: '700', fontSize: '1.25rem' }}>OrganicAI</span>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>&copy; {new Date().getFullYear()} Organic Marketing AI. All rights reserved.</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Stats shown are live platform data, updated in real-time.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
