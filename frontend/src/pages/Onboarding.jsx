import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Building2, Globe, Target, CreditCard, CheckCircle2, ArrowRight, Loader2, Bot, Cpu, ImageIcon } from 'lucide-react';
import { API_BASE, authFetch } from '../App';

const Onboarding = ({ user, token, showToast, updateAuth }) => {
  const [step, setStep] = useState(1);
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [businessModel, setBusinessModel] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // AI Analysis states
  const [analysisPhase, setAnalysisPhase] = useState(0); // 0=Extracting, 1=Brand Context, 2=Images
  
  const navigate = useNavigate();

  useEffect(() => {
    if (step === 3) {
      // Gradually progress the UI phases for visual feedback while polling
      const phaseInterval = setInterval(() => {
        setAnalysisPhase(prev => Math.min(prev + 1, 2));
      }, 3000);
      
      let active = true;
      const pollStatus = async () => {
        if (!active || step !== 3) return;
        
        try {
          const res = await authFetch(`${API_BASE}/users/me/onboarding-status`, {}, token);
          if (res.ok) {
            const data = await res.json();
            if (data.brandAnalysisComplete) {
              clearInterval(phaseInterval);
              setAnalysisPhase(3); // All complete
              setTimeout(() => { if (active) setStep(4); }, 600);
              return;
            }
          }
        } catch (err) {
          console.error('Polling error', err);
        }
        
        // Re-poll every 2 seconds
        if (active) setTimeout(pollStatus, 2000);
      };
      
      pollStatus();
      return () => {
        active = false;
        clearInterval(phaseInterval);
      };
    }
  }, [step, token]);

  const handleProfileSubmit = async () => {
    if (!businessModel) {
      showToast('Please select a business model', true);
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/users/me/business-profile`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          websiteUrl: website,
          description: description,
          businessModel: businessModel
        })
      });

      if (!res.ok) throw new Error('Failed to save profile');
      
      const updatedProfile = await res.json();
      updateAuth({ ...user, businessProfile: updatedProfile.data });
      showToast('Profile saved!');
      
      // Move to AI Analysis step
      setStep(3);
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handlePayment = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/users/me/subscribe`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) throw new Error('Payment simulation failed');
      
      updateAuth({ ...user, subscriptionStatus: 'ACTIVE' });
      showToast('Payment Successful! Subscription Activated.');
      navigate('/dashboard');
    } catch(err) {
      showToast(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="view centered-layout" style={{ position: 'relative' }}>
      
      {/* Background Decor */}
      <div style={{ position: 'absolute', top: '0', left: '0', width: '100%', height: '100%', background: 'radial-gradient(circle at 50% -20%, rgba(139, 92, 246, 0.15), transparent 60%)', zIndex: -1 }}></div>

      <div className="glass-panel card" style={{ maxWidth: '640px', padding: '3rem' }}>
        <div className="wizard-progress">
          <div className={`wizard-step ${step >= 1 ? 'active' : ''}`}></div>
          <div className={`wizard-step ${step >= 2 ? 'active' : ''}`}></div>
          <div className={`wizard-step ${step >= 3 ? 'active' : ''}`}></div>
          <div className={`wizard-step ${step >= 4 ? 'active' : ''}`}></div>
        </div>

        {step === 1 && (
          <div className="fade-in">
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
              <Building2 size={32} color="var(--primary-color)" />
              <h2 style={{ margin: 0 }}>Business Identity</h2>
            </div>
            <p style={{ marginBottom: '2.5rem', fontSize: '1.125rem' }}>Let's set up your core business details so our AI can understand your brand voice.</p>
            
            <div className="input-group">
              <label><Globe size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} /> Website URL</label>
              <input type="url" placeholder="https://example.com" value={website} onChange={e => setWebsite(e.target.value)} />
            </div>
            
            <div className="input-group">
              <label><Target size={16} style={{ verticalAlign: 'middle', marginRight: '0.5rem' }} /> Business Description</label>
              <textarea rows="4" placeholder="What does your business do? Who is your target audience?" value={description} onChange={e => setDescription(e.target.value)}></textarea>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '3rem' }}>
              <button className="btn btn-primary btn-large" onClick={() => {
                if(!website || !description) return showToast('Please fill all fields', true);
                setStep(2);
              }}>
                Continue <ArrowRight size={20} style={{ marginLeft: '0.5rem' }} />
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="fade-in">
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
              <Sparkles size={32} color="var(--primary-color)" />
              <h2 style={{ margin: 0 }}>Business Model</h2>
            </div>
            <p style={{ marginBottom: '2.5rem', fontSize: '1.125rem' }}>Select the category that best describes your business. This tunes the AI content generation engine.</p>
            
            <div className="selection-grid">
              {[
                { name: 'AI Influencer', icon: '🤖' },
                { name: 'SaaS', icon: '💻' },
                { name: 'E-commerce', icon: '🛒' },
                { name: 'Creator', icon: '🎨' },
                { name: 'Local Business', icon: '🏪' },
                { name: 'Agency', icon: '🤝' }
              ].map(model => (
                <div key={model.name} className={`selection-card ${businessModel === model.name ? 'selected' : ''}`} onClick={() => setBusinessModel(model.name)}>
                  <span className="selection-card-icon">{model.icon}</span>
                  {model.name}
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '3rem' }}>
              <button className="btn btn-secondary" onClick={() => setStep(1)}>Back</button>
              <button className="btn btn-primary btn-large" onClick={handleProfileSubmit} disabled={loading}>
                {loading ? <span className="spinner"></span> : <><span style={{ marginRight: '0.5rem' }}>Save & Generate</span> <ArrowRight size={20} /></>}
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="fade-in" style={{ textAlign: 'center', padding: '3rem 0' }}>
            <div style={{ position: 'relative', width: '120px', height: '120px', margin: '0 auto 3rem' }}>
              {/* Outer pulsing ring */}
              <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'rgba(168,85,247,0.2)', animation: 'pulseGlow 2s infinite' }}></div>
              {/* Inner spinner */}
              <div style={{ position: 'absolute', inset: '10px', borderRadius: '50%', border: '4px solid rgba(168,85,247,0.2)', borderTopColor: 'var(--primary-color)', animation: 'spin 1.5s linear infinite' }}></div>
              {/* Center icon */}
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Bot size={48} color="var(--primary-color)" />
              </div>
            </div>

            <h2 style={{ marginBottom: '2rem' }}>OrganicAI is working...</h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '400px', margin: '0 auto', textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', opacity: analysisPhase >= 0 ? 1 : 0.4 }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: analysisPhase > 0 ? 'var(--success)' : 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {analysisPhase > 0 ? <CheckCircle2 size={16} color="#fff" /> : <Globe size={16} />}
                </div>
                <div>
                  <span style={{ fontWeight: '600' }}>Extracting Website Data</span>
                  {analysisPhase === 0 && <span className="spinner" style={{ width: '12px', height: '12px', marginLeft: '8px', borderWidth: '1px' }}></span>}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', opacity: analysisPhase >= 1 ? 1 : 0.4 }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: analysisPhase > 1 ? 'var(--success)' : 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {analysisPhase > 1 ? <CheckCircle2 size={16} color="#fff" /> : <Cpu size={16} />}
                </div>
                <div>
                  <span style={{ fontWeight: '600' }}>Building Brand Context Engine</span>
                  {analysisPhase === 1 && <span className="spinner" style={{ width: '12px', height: '12px', marginLeft: '8px', borderWidth: '1px' }}></span>}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', opacity: analysisPhase >= 2 ? 1 : 0.4 }}>
                <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: analysisPhase > 2 ? 'var(--success)' : 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {analysisPhase > 2 ? <CheckCircle2 size={16} color="#fff" /> : <ImageIcon size={16} />}
                </div>
                <div>
                  <span style={{ fontWeight: '600' }}>Generating 3 Starter Creatives</span>
                  {analysisPhase === 2 && <span className="spinner" style={{ width: '12px', height: '12px', marginLeft: '8px', borderWidth: '1px' }}></span>}
                </div>
              </div>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="fade-in">
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
              <CreditCard size={32} color="var(--primary-color)" />
              <h2 style={{ margin: 0 }}>Brand Engine Ready!</h2>
            </div>
            <p style={{ marginBottom: '1.5rem', fontSize: '1.05rem', color: 'var(--text-muted)' }}>
              We analyzed your brand, generated custom content pillars, and created your first set of AI social posts & media. Activate Pro to unlock automated 2-hour publishing.
            </p>
            
            {/* Generated Brand Summary Preview */}
            <div style={{ background: 'rgba(139, 92, 246, 0.08)', border: '1px solid rgba(139, 92, 246, 0.25)', borderRadius: '16px', padding: '1.5rem', marginBottom: '2rem', textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', fontWeight: '700', color: 'var(--primary-color)' }}>
                <Sparkles size={18} /> Generated Brand Context Engine
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
                <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa' }}>Tone: Enterprise Professional</span>
                <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>Interval: Every 2 Hours (Aggressive)</span>
                <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc' }}>AI Auto-Pilot: Active</span>
              </div>
              <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}><strong>Content Pillars:</strong> Growth Tips • Industry Insights • Product Showcase • Thought Leadership</p>
            </div>

            <div className="payment-box">
              <h3 style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }}>PRO UNLIMITED</h3>
              <div className="price" style={{ margin: '1rem 0 1.5rem' }}>
                <span className="currency">$</span>17<span className="period">/mo</span>
              </div>
              
              <ul style={{ listStyle: 'none', textAlign: 'left', margin: '0 auto 2rem', maxWidth: '340px' }}>
                <li style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.5rem' }}><CheckCircle2 size={18} color="var(--primary-color)" /> Automated AI Creative Generation (Every 2h+)</li>
                <li style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.5rem' }}><CheckCircle2 size={18} color="var(--primary-color)" /> Auto-Populated Media Library</li>
                <li style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.5rem' }}><CheckCircle2 size={18} color="var(--primary-color)" /> Auto-Publishing (FB, IG, X, LinkedIn)</li>
              </ul>
              
              <button className="btn btn-primary btn-large" style={{ width: '100%' }} onClick={handlePayment} disabled={loading}>
                {loading ? 'Processing...' : 'Start 14-Day Free Trial'}
              </button>
              <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Secure payment processing. Cancel anytime.</p>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default Onboarding;
