import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, TrendingUp, Sparkles, Zap, PlayCircle, Users, ShieldCheck } from 'lucide-react';
import { Helmet } from 'react-helmet-async';

const Landing = () => {
  const navigate = useNavigate();

  const scrollToPricing = () => {
    document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="view">
      <Helmet>
        <title>OrganicAI | Automate your organic growth on autopilot</title>
        <meta name="description" content="The enterprise-grade AI marketing system built for SaaS, E-Commerce, and Influencers. Generate high-converting content and schedule it automatically across all platforms." />
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
              <Sparkles size={16} /> Now with Context-Aware AI Campaigns
            </div>
            <h1>Automate your <span className="gradient-text">organic growth</span> on autopilot.</h1>
            <p>The enterprise-grade AI marketing system built for SaaS, E-Commerce, and Influencers. Generate high-converting content and schedule it automatically across all platforms.</p>
            <div className="hero-cta">
              <button className="btn btn-primary btn-large" onClick={() => navigate('/auth')}>
                Start Automating Today <TrendingUp size={20} style={{ marginLeft: '0.5rem' }} />
              </button>
              <button className="btn btn-secondary btn-large" onClick={scrollToPricing}>
                View Pricing
              </button>
            </div>
            <div style={{ marginTop: '2rem', color: 'var(--text-muted)', fontSize: '0.875rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1.5rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="var(--success)"/> No credit card required</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="var(--success)"/> Cancel anytime</span>
            </div>
          </div>
          
          <div className="hero-stats">
            <div className="stat-card">
              <div className="stat-card-icon"><Zap size={32} /></div>
              <h3>SaaS & B2B</h3>
              <p>Generate highly-converting LinkedIn & X (Twitter) threads tailored for developers and B2B buyers. Drive demo bookings automatically.</p>
            </div>
            <div className="stat-card">
              <div className="stat-card-icon"><PlayCircle size={32} /></div>
              <h3>E-Commerce</h3>
              <p>Push engaging product videos, reels, & carousels directly to Instagram and Facebook. Turn organic views into immediate sales.</p>
            </div>
            <div className="stat-card">
              <div className="stat-card-icon"><Users size={32} /></div>
              <h3>AI Influencers</h3>
              <p>Maintain an active, hyper-engaging presence across all platforms without burning out. Let AI handle the daily grind.</p>
            </div>
          </div>
        </div>
      </header>

      {/* Social Proof / Integration Section */}
      <section style={{ padding: '4rem 0', background: 'rgba(0,0,0,0.3)', borderTop: '1px solid var(--border-color)', borderBottom: '1px solid var(--border-color)' }}>
        <div className="container" style={{ textAlign: 'center' }}>
          <h4 style={{ color: 'var(--text-muted)', marginBottom: '2rem', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Seamlessly connects with</h4>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '3rem', flexWrap: 'wrap', opacity: 0.6 }}>
            <h3 style={{ margin: 0, color: 'white' }}>Meta Graph API</h3>
            <h3 style={{ margin: 0, color: 'white' }}>X (Twitter) API</h3>
            <h3 style={{ margin: 0, color: 'white' }}>LinkedIn API</h3>
            <h3 style={{ margin: 0, color: 'white' }}>Resend Email</h3>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="pricing-section">
        <div className="container">
          <div className="pricing-header">
            <h2>Simple, transparent pricing.</h2>
            <p style={{ maxWidth: '600px', margin: '0 auto', fontSize: '1.125rem' }}>Everything you need to scale your organic presence, for one flat monthly rate. No hidden fees.</p>
          </div>
          
          <div className="pricing-card">
            <div className="pricing-card-header">
              <h3 style={{ color: 'var(--primary-color)', marginBottom: '1rem' }}>PRO TIER</h3>
              <div className="price">
                <span className="currency">$</span>17<span className="period">/mo</span>
              </div>
              <p style={{ marginTop: '1rem', color: 'var(--text-main)' }}>Full access to the Organic Marketing AI platform.</p>
            </div>
            
            <ul className="pricing-features">
              <li><CheckCircle2 size={20} /> <span><strong>Unlimited</strong> AI Content Generation</span></li>
              <li><CheckCircle2 size={20} /> <span>Facebook & Instagram Automation</span></li>
              <li><CheckCircle2 size={20} /> <span>X (Twitter) & LinkedIn Integration</span></li>
              <li><CheckCircle2 size={20} /> <span>Custom Business Context Engine</span></li>
              <li><CheckCircle2 size={20} /> <span>Automated Email Marketing Drips</span></li>
              <li><CheckCircle2 size={20} /> <span>Advanced Engagement Analytics</span></li>
            </ul>
            
            <button className="btn btn-primary" style={{ width: '100%', padding: '1.25rem', fontSize: '1.125rem' }} onClick={() => navigate('/auth')}>
              Get Started for $17 <Sparkles size={20} style={{ marginLeft: '0.5rem' }} />
            </button>
            <p style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} /> Secure payment processing
            </p>
          </div>
        </div>
      </section>
      
      {/* Footer */}
      <footer style={{ padding: '4rem 0 2rem', borderTop: '1px solid var(--border-color)', textAlign: 'center' }}>
        <div className="container">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Sparkles size={20} color="var(--primary-color)" />
            <span style={{ fontWeight: '700', fontSize: '1.25rem' }}>OrganicAI</span>
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>&copy; {new Date().getFullYear()} Organic Marketing AI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
