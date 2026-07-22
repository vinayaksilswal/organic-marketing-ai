import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle2, TrendingUp, Sparkles, Zap, PlayCircle, Users, 
  ShieldCheck, ChevronDown, MessageSquare, ArrowRight, Star,
  BarChart3, Link, Target
} from 'lucide-react';
import { Helmet } from 'react-helmet-async';

const Landing = () => {
  const navigate = useNavigate();
  const [activeFaq, setActiveFaq] = useState(null);

  const scrollToPricing = () => {
    document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleFaq = (index) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  const faqs = [
    {
      question: "Do I need technical skills to use OrganicAI?",
      answer: "Not at all. We built OrganicAI to be as simple as connecting your social accounts and telling us your target audience. Our AI handles the generation, scheduling, and posting automatically."
    },
    {
      question: "Can I review the content before it's posted?",
      answer: "Yes! While you can put it on full autopilot, we also offer a 'Review Mode' where you can approve, edit, or reject AI-generated drafts before they go live."
    },
    {
      question: "Which platforms do you currently support?",
      answer: "We currently support direct integrations with LinkedIn, X (Twitter), Facebook, and Instagram. We are constantly working on adding more platforms like TikTok and Pinterest."
    },
    {
      question: "Is there a long-term contract?",
      answer: "No, our pricing is strictly month-to-month. You can cancel at any time directly from your dashboard with just two clicks, no questions asked."
    },
    {
      question: "Will the AI sound like a robot?",
      answer: "Our Custom Business Context Engine analyzes your brand voice, previous posts, and target audience to write exactly like you do. Over time, it learns what gets the highest engagement."
    }
  ];

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
                  <div style={{ flex: 1, height: '100px', background: 'rgba(139, 92, 246, 0.1)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '12px' }}></div>
                  <div style={{ flex: 1, height: '100px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '12px' }}></div>
                  <div style={{ flex: 1, height: '100px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '12px' }}></div>
                </div>
                <div style={{ width: '100%', height: '200px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px' }}></div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Social Proof Ticker */}
      <section className="social-proof-section">
        <div className="ticker-wrap">
          <div className="ticker-content">
            <div className="ticker-item">
              <span className="ticker-value">50M+</span>
              <span className="ticker-label">Impressions Generated</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">10,000+</span>
              <span className="ticker-label">Hours Saved</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">85%</span>
              <span className="ticker-label">Higher Engagement</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">4.9/5</span>
              <span className="ticker-label">Customer Rating</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">2,500+</span>
              <span className="ticker-label">Active Users</span>
            </div>
            {/* Duplicates for seamless looping */}
            <div className="ticker-item">
              <span className="ticker-value">50M+</span>
              <span className="ticker-label">Impressions Generated</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">10,000+</span>
              <span className="ticker-label">Hours Saved</span>
            </div>
            <div className="ticker-item">
              <span className="ticker-value">85%</span>
              <span className="ticker-label">Higher Engagement</span>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works-section">
        <div className="container">
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Workflow</h4>
            <h2>Growth on Autopilot in 3 Steps</h2>
            <p style={{ maxWidth: '600px', margin: '0 auto' }}>You don't need to be a marketing expert. OrganicAI streamlines your entire organic funnel from ideation to distribution.</p>
          </div>
          
          <div className="how-it-works-grid">
            <div className="step-card">
              <div className="step-number"><Link size={32} /></div>
              <h3>1. Connect</h3>
              <p>Link your social profiles and define your brand voice, target audience, and niche. Takes less than 2 minutes.</p>
            </div>
            <div className="step-card">
              <div className="step-number"><Target size={32} /></div>
              <h3>2. Generate</h3>
              <p>Our AI analyzes viral trends in your niche and drafts high-converting posts, threads, and scripts perfectly tailored for you.</p>
            </div>
            <div className="step-card">
              <div className="step-number"><BarChart3 size={32} /></div>
              <h3>3. Grow</h3>
              <p>Content is automatically scheduled and published at peak times. Watch your impressions, followers, and revenue scale.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Features/Use Cases */}
      <section style={{ padding: '4rem 0' }}>
        <div className="container">
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
      </section>

      {/* Testimonials / Wall of Love */}
      <section className="testimonials-section">
        <div className="container">
          <div style={{ textAlign: 'center' }}>
            <h4 style={{ color: 'var(--primary-color)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Wall of Love</h4>
            <h2>Trusted by creators and founders</h2>
          </div>
          
          <div className="testimonial-grid">
            <div className="testimonial-card">
              <div className="stars">
                <Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" />
              </div>
              <p className="testimonial-text">"OrganicAI completely replaced our social media manager. It writes better LinkedIn posts than I do and scheduling is a breeze. My inbound leads went up 40% in month one."</p>
              <div className="testimonial-author">
                <div className="author-avatar">S</div>
                <div className="author-info">
                  <h4>Sarah Jenkins</h4>
                  <p>Founder, TechFlow SaaS</p>
                </div>
              </div>
            </div>
            
            <div className="testimonial-card">
              <div className="stars">
                <Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" />
              </div>
              <p className="testimonial-text">"I was struggling to keep up with Twitter and Instagram while running my agency. This tool gave me 10 hours a week back. The AI actually understands my niche."</p>
              <div className="testimonial-author">
                <div className="author-avatar">M</div>
                <div className="author-info">
                  <h4>Marcus Chen</h4>
                  <p>Digital Agency Owner</p>
                </div>
              </div>
            </div>
            
            <div className="testimonial-card">
              <div className="stars">
                <Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" /><Star size={16} fill="currentColor" />
              </div>
              <p className="testimonial-text">"The context engine is insane. It read my previous blog posts and now writes threads that sound exactly like me. My follower count has doubled in 6 weeks."</p>
              <div className="testimonial-author">
                <div className="author-avatar">E</div>
                <div className="author-info">
                  <h4>Elena Rodriguez</h4>
                  <p>E-commerce Brand Creator</p>
                </div>
              </div>
            </div>
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

      {/* FAQ Section */}
      <section className="faq-section">
        <div className="container">
          <div style={{ textAlign: 'center' }}>
            <h2>Frequently Asked Questions</h2>
            <p>Everything you need to know about the product and billing.</p>
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
          <h2 style={{ fontSize: '3rem', marginBottom: '1.5rem' }}>Ready to scale your organic growth?</h2>
          <p style={{ fontSize: '1.25rem', maxWidth: '600px', margin: '0 auto 2.5rem' }}>
            Join thousands of creators and businesses who are automating their marketing and driving real revenue.
          </p>
          <button className="btn btn-primary btn-large" onClick={() => navigate('/auth')}>
            Start Your Journey <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
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
        </div>
      </footer>
    </div>
  );
};

export default Landing;
