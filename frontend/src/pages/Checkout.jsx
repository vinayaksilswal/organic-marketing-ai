import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import { Sparkles, CheckCircle2, ShieldCheck, LogOut } from 'lucide-react';
import '../styles/auth.css'; // Reuse auth styles

export default function Checkout({ user, onLogout }) {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  // If user is already active, they shouldn't be here
  if (user?.subscriptionStatus === 'ACTIVE') {
    navigate('/dashboard');
    return null;
  }

  const handleApprove = (data, actions) => {
    // PayPal returns a subscription ID in data.subscriptionID
    // The backend webhook will handle the actual activation
    console.log("Subscription approved:", data);
    
    // Optistic redirect after brief delay
    setTimeout(() => {
      window.location.href = '/dashboard';
    }, 3000);
  };

  const initialOptions = {
    "client-id": import.meta.env.VITE_PAYPAL_CLIENT_ID || "test",
    "vault": "true",
    "intent": "subscription",
    "components": "buttons",
    "disable-funding": "card"
  };

  return (
    <div className="auth-container">
      {/* Reusing the beautiful split layout from Auth */}
      <div className="auth-left">
        <div className="auth-logo" onClick={() => navigate('/')} style={{cursor: 'pointer'}}>
          <Sparkles className="logo-icon" size={28} />
          <span className="logo-text">OrganicAI</span>
        </div>
        
        <div className="auth-content-wrapper">
          <div className="auth-header" style={{ marginBottom: '2rem' }}>
            <h1>Complete your subscription</h1>
            <p>You're almost there! Activate your Pro Plan to access the dashboard.</p>
          </div>

          {error && <div className="error-message" style={{marginBottom: '1rem', color: '#ef4444'}}>{error}</div>}

          <div className="pricing-card glass-card" style={{ padding: '2rem', marginBottom: '2rem', background: 'rgba(255, 255, 255, 0.03)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <div>
                <h3 style={{ color: 'var(--primary-color)', margin: 0 }}>PRO PLAN</h3>
                <p style={{ margin: 0, color: 'var(--text-muted)' }}>Billed Monthly</p>
              </div>
              <div className="price" style={{ fontSize: '2rem', fontWeight: 'bold' }}>
                <span className="currency" style={{ fontSize: '1rem' }}>$</span>17<span className="period" style={{ fontSize: '1rem' }}>/mo</span>
              </div>
            </div>

            <ul className="pricing-features" style={{ listStyle: 'none', padding: 0, margin: '0 0 2rem 0' }}>
              <li style={{ display: 'flex', alignItems: 'center', marginBottom: '0.75rem' }}><CheckCircle2 size={18} color="var(--primary-color)" style={{ marginRight: '0.5rem' }} /> <span>AI Brand Context Engine</span></li>
              <li style={{ display: 'flex', alignItems: 'center', marginBottom: '0.75rem' }}><CheckCircle2 size={18} color="var(--primary-color)" style={{ marginRight: '0.5rem' }} /> <span>Unlimited AI Creative Generation</span></li>
              <li style={{ display: 'flex', alignItems: 'center', marginBottom: '0.75rem' }}><CheckCircle2 size={18} color="var(--primary-color)" style={{ marginRight: '0.5rem' }} /> <span>AI Video Studio (Veo 3.1)</span></li>
              <li style={{ display: 'flex', alignItems: 'center', marginBottom: '0.75rem' }}><CheckCircle2 size={18} color="var(--primary-color)" style={{ marginRight: '0.5rem' }} /> <span>Social & Email Automation</span></li>
            </ul>

            <div className="paypal-button-container" style={{ minHeight: '150px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {import.meta.env.VITE_PAYPAL_CLIENT_ID ? (
                <PayPalScriptProvider options={initialOptions}>
                  <PayPalButtons
                    style={{ layout: "vertical", shape: "rect", color: "gold" }}
                    createSubscription={(data, actions) => {
                      return actions.subscription.create({
                        'plan_id': import.meta.env.VITE_PAYPAL_PLAN_ID || "P-YOUR_PLAN_ID",
                        'custom_id': user?.id // CRITICAL: This links the payment to our user in the webhook!
                      });
                    }}
                    onApprove={handleApprove}
                    onError={(err) => {
                      console.error("PayPal Error:", err);
                      setError("Payment could not be processed. Please try again.");
                    }}
                  />
                </PayPalScriptProvider>
              ) : (
                <div style={{ padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: '8px', textAlign: 'center' }}>
                  PayPal Client ID not configured.
                </div>
              )}
            </div>
            
            <p style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} /> Secure payment processing via PayPal
            </p>
          </div>
          
          <button 
            className="btn btn-outline" 
            onClick={onLogout}
            style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
          >
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </div>
      
      <div className="auth-right">
        <div className="glow-orb top-left"></div>
        <div className="glow-orb bottom-right"></div>
        
        <div className="auth-showcase">
          <div className="showcase-card glass-card">
            <div className="showcase-header">
              <div className="mock-dot"></div>
              <div className="mock-dot"></div>
              <div className="mock-dot"></div>
            </div>
            <div className="showcase-body">
              <h3 style={{marginBottom: '1rem'}}>Ready to scale your organic reach?</h3>
              <p style={{color: 'var(--text-muted)', lineHeight: '1.6'}}>
                "OrganicAI replaced our entire content team. The video studio alone generates 10x ROI for our jewelry brand every single month."
              </p>
              <div style={{marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem'}}>
                <div style={{width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))'}}></div>
                <div>
                  <div style={{fontWeight: 'bold'}}>Sarah Jenkins</div>
                  <div style={{fontSize: '0.875rem', color: 'var(--text-muted)'}}>Founder, Lumina Jewelry</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
