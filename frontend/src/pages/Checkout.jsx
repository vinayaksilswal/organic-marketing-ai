import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import { Sparkles, CheckCircle2, ShieldCheck, LogOut } from 'lucide-react';

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
    <div className="view centered-layout" style={{ position: 'relative' }}>
      
      {/* Background Decor */}
      <div style={{ position: 'absolute', top: '10%', left: '20%', width: '300px', height: '300px', background: 'var(--primary-color)', filter: 'blur(100px)', opacity: '0.2', borderRadius: '50%', zIndex: -1 }}></div>
      <div style={{ position: 'absolute', bottom: '10%', right: '20%', width: '400px', height: '400px', background: 'var(--secondary-color)', filter: 'blur(120px)', opacity: '0.15', borderRadius: '50%', zIndex: -1 }}></div>

      <div className="glass-panel card" style={{ padding: '3.5rem', maxWidth: '600px', width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '2rem' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '1rem', borderRadius: '50%', border: '1px solid rgba(139, 92, 246, 0.2)', cursor: 'pointer' }} onClick={() => navigate('/')}>
            <Sparkles size={32} color="var(--primary-color)" />
          </div>
        </div>
        
        <h2 style={{ textAlign: 'center', marginBottom: '0.5rem' }}>Complete your subscription</h2>
        <p style={{ textAlign: 'center', marginBottom: '2.5rem', fontSize: '1.125rem' }}>
          You're almost there! Activate your Pro Plan to access the dashboard.
        </p>

        {error && <div className="message error" style={{position: 'relative', bottom: 'auto', right: 'auto', marginBottom: '2rem'}}>{error}</div>}

        <div className="pricing-card" style={{ padding: '2rem', marginBottom: '2rem', maxWidth: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
            <div>
              <h3 style={{ color: 'var(--primary-color)', margin: 0 }}>PRO PLAN</h3>
              <p style={{ margin: 0, color: 'var(--text-muted)' }}>Billed Monthly</p>
            </div>
            <div className="price" style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>
              <span className="currency" style={{ fontSize: '1.25rem', marginTop: 0 }}>$</span>17<span className="period" style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>/mo</span>
            </div>
          </div>

          <ul className="pricing-features" style={{ padding: 0, margin: '0 0 2rem 0' }}>
            <li><CheckCircle2 size={20} /> <span>AI Brand Context Engine</span></li>
            <li><CheckCircle2 size={20} /> <span>Unlimited AI Creative Generation</span></li>
            <li><CheckCircle2 size={20} /> <span>AI Video Studio (Veo 3.1)</span></li>
            <li><CheckCircle2 size={20} /> <span>Social & Email Automation</span></li>
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
          className="btn btn-secondary" 
          onClick={onLogout}
          style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
        >
          <LogOut size={16} /> Sign out
        </button>
      </div>
    </div>
  );
}
