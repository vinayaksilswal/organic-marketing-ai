import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle2, TrendingUp, Sparkles, Zap, PlayCircle, Users, 
  ShieldCheck, ChevronDown, ArrowRight, Star,
  BarChart3, Link, Target, Clock, Bot, Eye, DollarSign,
  Layers, Cpu, Globe, Lock, RefreshCw
} from 'lucide-react';
import { Helmet } from 'react-helmet-async';

const API_BASE = import.meta.env.VITE_API_URL || 'https://organic-marketing-ai.onrender.com/api/v1';
const PUBLIC_API = API_BASE.replace('/api/v1', '');

const Landing = () => {
  const navigate = useNavigate();
  const [activeFaq, setActiveFaq] = useState(null);
  const [liveStats, setLiveStats] = useState(null);
  const [recentActivity, setRecentActivity] = useState([]);
  
  // ROI Calculator state
  const [hourlyRate, setHourlyRate] = useState(50);
  const [hoursPerWeek, setHoursPerWeek] = useState(10);

  // Fetch live platform stats
  useEffect(() => {
    fetch(`${PUBLIC_API}/api/public/stats`)
      .then(r => r.json())
      .then(data => setLiveStats(data))
      .catch(() => {});

    fetch(`${PUBLIC_API}/api/public/recent-activity`)
      .then(r => r.json())
      .then(data => { if (data?.data) setRecentActivity(data.data); })
      .catch(() => {});
  }, []);

  const scrollToPricing = () => {
    document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleFaq = (index) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  const monthlySavings = ((hoursPerWeek * 4) * hourlyRate) - 17;
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
      answer: "We currently support direct integrations with Facebook, Instagram, X (Twitter), and LinkedIn. Content is generated and optimized for each platform's format and audience."
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
    <div className="view">
      <Helmet>
        <title>OrganicAI — AI writes, designs, and posts your marketing content automatically</title>
        <meta name="description" content="OrganicAI auto-generates brand-matched social media posts with AI images and publishes them to Facebook, Instagram, X, and LinkedIn on a schedule you control. Starting at $17/mo." />
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
      <nav className="navbar">
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', padding: '0' }}>
          <div className="nav-brand">
            <Sparkles size={24} color="var(--primary-color)" />
            <span>OrganicAI</span>
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <button className="btn btn-secondary" onClick={() => navigate('/auth')}>Log in</button>
            <button className="btn btn-primary" onClick={() => navigate('/auth')}>Start for $17</button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero">
        <div className="container">
          <div className="hero-content">
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)', padding: '0.5rem 1rem', borderRadius: '999px', marginBottom: '2rem', color: 'var(--primary-color)', fontWeight: '600', fontSize: '0.875rem' }}>
              <Cpu size={16} /> AI Brand Context Engine + Auto-Generated Creatives
            </div>
            <h1>AI writes, designs, and posts your marketing — <span className="gradient-text">every 2 hours</span>, automatically.</h1>
            <p style={{ fontSize: '1.2rem', maxWidth: '680px', margin: '0 auto', lineHeight: 1.7 }}>
              Describe your business once. OrganicAI analyzes your brand, generates on-brand posts with AI images, and publishes them to <strong>Facebook, Instagram, X, and LinkedIn</strong> on a schedule you control.
            </p>
            <div className="hero-cta">
              <button className="btn btn-primary btn-large" onClick={() => navigate('/auth')}>
                Start Automating — $17/mo <TrendingUp size={20} style={{ marginLeft: '0.5rem' }} />
              </button>
              <button className="btn btn-secondary btn-large" onClick={scrollToPricing}>
                See What's Included
              </button>
            </div>
            <div style={{ marginTop: '2rem', color: 'var(--text-muted)', fontSize: '0.875rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="var(--success)"/> No credit card to start</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="var(--success)"/> Cancel anytime</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="var(--success)"/> AI creatives on signup</span>
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
              <div className="mockup-content">
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
                  <div style={{ flex: 1, height: '100px', background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '12px', padding: '1rem', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>Posts Generated</span>
                    <span style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--primary-color)' }}>{liveStats?.posts || 0}</span>
                  </div>
                  <div style={{ flex: 1, height: '100px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '12px', padding: '1rem', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>Campaigns Active</span>
                    <span style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--secondary-color)' }}>{liveStats?.campaigns || 0}</span>
                  </div>
                  <div style={{ flex: 1, height: '100px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '12px', padding: '1rem', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>Businesses</span>
                    <span style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--success)' }}>{liveStats?.workspaces || 0}</span>
                  </div>
                </div>
                <div style={{ width: '100%', height: '200px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px' }}></div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Live Stats Ticker — Real Data */}
      <section className="social-proof-section">
        <div className="ticker-wrap">
          <div className="ticker-content">
            <div className="ticker-item">
              <span className="ticker-value">{liveStats?.posts || '—'}</span>
              <span className="ticker-label">Posts Generated (Live)</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">4</span>
              <span className="ticker-label">Platforms Supported</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">&lt;2 min</span>
              <span className="ticker-label">Setup Time</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">$17</span>
              <span className="ticker-label">Flat Monthly Rate</span>
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
              <span className="ticker-value">4</span>
              <span className="ticker-label">Platforms Supported</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">&lt;2 min</span>
              <span className="ticker-label">Setup Time</span>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works-section">
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>How It Works</h4>
            <h2>From signup to automated posts in 3 steps</h2>
            <p style={{ maxWidth: '640px', margin: '0 auto', fontSize: '1.05rem' }}>No marketing expertise required. OrganicAI's Brand Context Engine does the heavy lifting.</p>
          </div>
          
          <div className="how-it-works-grid">
            <div className="step-card">
              <div className="step-number"><Bot size={32} /></div>
              <h3>1. Describe Your Business</h3>
              <p>Enter your business name, website, and a short description. Our AI builds a complete Brand Context Profile — tone of voice, content pillars, hashtags, and audience targeting.</p>
            </div>
            <div className="step-card">
              <div className="step-number"><Layers size={32} /></div>
              <h3>2. AI Generates Creatives</h3>
              <p>OrganicAI auto-creates branded social posts with AI-generated images. Review them, or turn on auto-approve and let the engine handle everything.</p>
            </div>
            <div className="step-card">
              <div className="step-number"><RefreshCw size={32} /></div>
              <h3>3. Automated Publishing</h3>
              <p>Set your interval (default: every 2 hours). OrganicAI publishes content to Facebook, Instagram, X, and LinkedIn automatically. Watch your analytics grow.</p>
            </div>
          </div>
        </div>
      </section>

      {/* What Makes This Different — Genuine Value Props */}
      <section style={{ padding: '5rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Built Different</h4>
            <h2>Not another "schedule your posts" tool</h2>
            <p style={{ maxWidth: '640px', margin: '0.5rem auto 0', fontSize: '1.05rem' }}>Most tools just schedule what you write. OrganicAI writes, designs, and publishes — so you never touch content creation again.</p>
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
      <section id="roi" style={{ padding: '5rem 0' }}>
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>ROI Calculator</h4>
            <h2>See how much you'll save</h2>
            <p style={{ maxWidth: '600px', margin: '0.5rem auto 0' }}>Calculate the real cost of doing marketing manually vs letting AI handle it.</p>
          </div>

          <div className="glass-panel" style={{ maxWidth: '700px', margin: '0 auto', padding: '3rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2.5rem' }}>
              <div className="input-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><DollarSign size={16} /> Your Hourly Rate ($)</label>
                <input type="number" value={hourlyRate} onChange={e => setHourlyRate(Number(e.target.value) || 0)} min="1" />
              </div>
              <div className="input-group">
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Clock size={16} /> Hours/Week on Marketing</label>
                <input type="number" value={hoursPerWeek} onChange={e => setHoursPerWeek(Number(e.target.value) || 0)} min="1" />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1.5rem', textAlign: 'center' }}>
              <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '1.5rem', borderRadius: '16px' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0 0 0.5rem 0' }}>Manual Cost / Month</p>
                <p style={{ fontSize: '2rem', fontWeight: '800', color: '#ef4444', margin: 0 }}>${(hoursPerWeek * 4 * hourlyRate).toLocaleString()}</p>
              </div>
              <div style={{ background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.2)', padding: '1.5rem', borderRadius: '16px' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0 0 0.5rem 0' }}>OrganicAI Cost</p>
                <p style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--primary-color)', margin: 0 }}>$17</p>
              </div>
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '1.5rem', borderRadius: '16px' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0 0 0.5rem 0' }}>You Save / Year</p>
                <p style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--success)', margin: 0 }}>${Math.max(0, yearlySavings).toLocaleString()}</p>
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

      {/* Pricing Section */}
      <section id="pricing" className="pricing-section">
        <div className="container">
          <div className="pricing-header">
            <h2>One plan. Everything included.</h2>
            <p style={{ maxWidth: '600px', margin: '0 auto', fontSize: '1.125rem' }}>No tiers, no hidden limits, no upsells. Every feature is available for one flat rate.</p>
          </div>
          
          <div className="pricing-card">
            <div className="pricing-card-header">
              <h3 style={{ color: 'var(--primary-color)', marginBottom: '1rem' }}>PRO PLAN</h3>
              <div className="price">
                <span className="currency">$</span>17<span className="period">/mo</span>
              </div>
              <p style={{ marginTop: '1rem', color: 'var(--text-main)' }}>Full access to the entire OrganicAI platform.</p>
            </div>
            
            <ul className="pricing-features">
              <li><CheckCircle2 size={20} /> <span><strong>AI Brand Context Engine</strong> — auto-analyzes your business</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>AI Creative Generation</strong> — posts + images on demand</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>4 Platform Publishing</strong> — FB, IG, X, LinkedIn</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>Autopilot Scheduling</strong> — 2hr, 4hr, 8hr, or custom</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>Multi-Workspace</strong> — unlimited brand workspaces</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>E-Commerce Catalog Sync</strong> — import products</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>Email Marketing Drips</strong> — automated email campaigns</span></li>
              <li><CheckCircle2 size={20} /> <span><strong>AI Video Studio</strong> — promotional video generation</span></li>
            </ul>
            
            <button className="btn btn-primary" style={{ width: '100%', padding: '1.25rem', fontSize: '1.125rem' }} onClick={() => navigate('/auth')}>
              Get Started — $17/mo <Sparkles size={20} style={{ marginLeft: '0.5rem' }} />
            </button>
            <p style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} /> Secure payment · Cancel anytime · No setup fees
            </p>
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
        <div className="container">
          <h2 style={{ fontSize: '3rem', marginBottom: '1.5rem' }}>Ready to automate your organic growth?</h2>
          <p style={{ fontSize: '1.25rem', maxWidth: '640px', margin: '0 auto 2.5rem' }}>
            Describe your business once. OrganicAI handles everything else — AI content, AI images, automated publishing, across 4 platforms.
          </p>
          <button className="btn btn-primary btn-large" onClick={() => navigate('/auth')}>
            Start Your Free Trial <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
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
