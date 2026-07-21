import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Building2, Globe, Target, CreditCard, CheckCircle2, ArrowRight } from 'lucide-react';
import { API_BASE } from '../App';

const Onboarding = ({ user, token, showToast, updateAuth }) => {
  const [step, setStep] = useState(1);
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [businessModel, setBusinessModel] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

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
                {loading ? <span className="spinner"></span> : <><span style={{ marginRight: '0.5rem' }}>Save & Continue</span> <ArrowRight size={20} /></>}
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="fade-in">
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
              <CreditCard size={32} color="var(--primary-color)" />
              <h2 style={{ margin: 0 }}>Activate Pro</h2>
            </div>
            <p style={{ marginBottom: '2.5rem', fontSize: '1.125rem' }}>You're almost there. Activate your Pro plan to unlock the dashboard and start automating your growth.</p>
            
            <div className="payment-box">
              <h3 style={{ color: 'var(--primary-color)', marginBottom: '0.5rem' }}>PRO TIER</h3>
              <div className="price" style={{ margin: '1rem 0 2rem' }}>
                <span className="currency">$</span>17<span className="period">/mo</span>
              </div>
              
              <ul style={{ listStyle: 'none', textAlign: 'left', margin: '0 auto 2.5rem', maxWidth: '300px' }}>
                <li style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.5rem' }}><CheckCircle2 size={18} color="var(--primary-color)" /> Unlimited AI Content</li>
                <li style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.5rem' }}><CheckCircle2 size={18} color="var(--primary-color)" /> Automated Scheduling</li>
                <li style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.5rem' }}><CheckCircle2 size={18} color="var(--primary-color)" /> All Social Platforms</li>
              </ul>
              
              <button className="btn btn-primary btn-large" style={{ width: '100%' }} onClick={handlePayment} disabled={loading}>
                {loading ? 'Processing...' : 'Complete Payment (Mock $17)'}
              </button>
              <p style={{ marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>Secure payment processing via Stripe/PayPal</p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-start', marginTop: '2rem' }}>
              <button className="btn btn-secondary" onClick={() => setStep(2)}>Back</button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default Onboarding;
