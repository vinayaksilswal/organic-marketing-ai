import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PayPalScriptProvider, PayPalButtons } from "@paypal/react-paypal-js";
import { Sparkles, CheckCircle2, ShieldCheck, LogOut, CreditCard, Building2 } from 'lucide-react';

export default function Checkout({ user, onLogout }) {
  const navigate = useNavigate();
  const [error, setError] = useState(null);
  const [paymentMethod, setPaymentMethod] = useState('stripe'); // 'paypal' or 'stripe'

  if (user?.subscriptionStatus === 'ACTIVE') {
    navigate('/dashboard');
    return null;
  }

  const handleApprove = (data, actions) => {
    console.log("Subscription approved:", data);
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
    <div className="view centered-layout" style={{ position: 'relative', minHeight: '100vh', padding: '2rem' }}>
      <div style={{ position: 'absolute', top: '10%', left: '20%', width: '300px', height: '300px', background: 'var(--primary-color)', filter: 'blur(100px)', opacity: '0.2', borderRadius: '50%', zIndex: -1 }}></div>
      <div style={{ position: 'absolute', bottom: '10%', right: '20%', width: '400px', height: '400px', background: 'var(--secondary-color)', filter: 'blur(120px)', opacity: '0.15', borderRadius: '50%', zIndex: -1 }}></div>

      <div className="glass-panel card" style={{ padding: '3.5rem', maxWidth: '900px', width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '2rem' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.1)', padding: '1rem', borderRadius: '50%', border: '1px solid rgba(139, 92, 246, 0.2)', cursor: 'pointer' }} onClick={() => navigate('/')}>
            <Sparkles size={32} color="var(--primary-color)" />
          </div>
        </div>
        
        <h2 style={{ textAlign: 'center', marginBottom: '0.5rem' }}>Choose your plan</h2>
        <p style={{ textAlign: 'center', marginBottom: '2.5rem', fontSize: '1.125rem', color: 'var(--text-muted)' }}>
          Activate your account to access the dashboard and automation tools.
        </p>

        {error && <div className="message error" style={{marginBottom: '2rem', width: '100%'}}>{error}</div>}

        <div style={{ display: 'flex', gap: '2rem', width: '100%', flexWrap: 'wrap', justifyContent: 'center' }}>
          {/* Pro Plan Card */}
          <div className="pricing-card" style={{ flex: '1 1 350px', padding: '2rem', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
              <div>
                <h3 style={{ color: 'var(--primary-color)', margin: 0 }}>PRO PLAN</h3>
                <p style={{ margin: 0, color: 'var(--text-muted)' }}>Billed Monthly</p>
              </div>
              <div className="price" style={{ fontSize: '2.5rem', fontWeight: 'bold' }}>
                <span className="currency" style={{ fontSize: '1.25rem', marginTop: 0 }}>$</span>17<span className="period" style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>/mo</span>
              </div>
            </div>

            <ul className="pricing-features" style={{ padding: 0, margin: '0 0 2rem 0', flexGrow: 1 }}>
              <li><CheckCircle2 size={20} /> <span>AI Brand Context Engine</span></li>
              <li><CheckCircle2 size={20} /> <span>Unlimited AI Creative Generation</span></li>
              <li><CheckCircle2 size={20} /> <span>AI Video Studio (Veo 3.1)</span></li>
              <li><CheckCircle2 size={20} /> <span>Social & Email Automation</span></li>
            </ul>

            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
              <button 
                className={`btn ${paymentMethod === 'stripe' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1, padding: '0.75rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
                onClick={() => setPaymentMethod('stripe')}
              >
                <CreditCard size={18} /> Card
              </button>
              <button 
                className={`btn ${paymentMethod === 'paypal' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1, padding: '0.75rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
                onClick={() => setPaymentMethod('paypal')}
              >
                PayPal
              </button>
            </div>

            <div className="payment-container" style={{ minHeight: '150px', display: 'flex', flexDirection: 'column', gap: '1rem', justifyContent: 'center' }}>
              {paymentMethod === 'stripe' && (
                <button 
                  className="btn btn-primary" 
                  style={{ width: '100%', padding: '1rem', fontSize: '1.125rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
                  onClick={() => alert("Stripe checkout integration pending.")}
                >
                  <CreditCard size={20} /> Pay with Stripe
                </button>
              )}
              {paymentMethod === 'paypal' && (
                import.meta.env.VITE_PAYPAL_CLIENT_ID ? (
                  <PayPalScriptProvider options={initialOptions}>
                    <PayPalButtons
                      style={{ layout: "vertical", shape: "rect", color: "gold" }}
                      createSubscription={(data, actions) => {
                        return actions.subscription.create({
                          'plan_id': import.meta.env.VITE_PAYPAL_PLAN_ID || "P-YOUR_PLAN_ID",
                          'custom_id': user?.id
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
                    PayPal Client ID not configured. Please use Card payment.
                  </div>
                )
              )}
            </div>
            
            <p style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              <ShieldCheck size={14} style={{ verticalAlign: 'middle', marginRight: '0.25rem' }} /> Secure payment processing
            </p>
          </div>

          {/* Enterprise Plan Card */}
          <div className="pricing-card" style={{ flex: '1 1 350px', padding: '2rem', display: 'flex', flexDirection: 'column', background: 'linear-gradient(145deg, rgba(20,20,20,0.8), rgba(30,30,30,0.9))', border: '1px solid rgba(255,255,255,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
              <div>
                <h3 style={{ color: 'white', margin: 0 }}>ENTERPRISE</h3>
                <p style={{ margin: 0, color: 'var(--text-muted)' }}>Custom Solutions</p>
              </div>
              <div className="price" style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                Custom
              </div>
            </div>

            <ul className="pricing-features" style={{ padding: 0, margin: '0 0 2rem 0', flexGrow: 1 }}>
              <li><CheckCircle2 size={20} /> <span>Dedicated Account Manager</span></li>
              <li><CheckCircle2 size={20} /> <span>Custom AI Model Training</span></li>
              <li><CheckCircle2 size={20} /> <span>SAML & SSO Integration</span></li>
              <li><CheckCircle2 size={20} /> <span>SLA & Priority Support</span></li>
            </ul>

            <button 
              className="btn btn-secondary" 
              style={{ width: '100%', padding: '1rem', fontSize: '1.125rem', marginTop: 'auto', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', border: '1px solid rgba(255,255,255,0.3)', color: 'white' }}
              onClick={() => window.location.href = "mailto:sales@organicai.com"}
            >
              <Building2 size={20} /> Contact Sales
            </button>
          </div>
        </div>
        
        <button 
          className="btn btn-secondary" 
          onClick={onLogout}
          style={{ marginTop: '2rem', padding: '0.75rem 1.5rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', background: 'transparent', border: 'none' }}
        >
          <LogOut size={16} /> Sign out
        </button>
      </div>
    </div>
  );
}
