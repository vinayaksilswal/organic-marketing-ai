import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

export default function CookieBanner() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem('cookie_consent');
    if (!consent) {
      setIsVisible(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cookie_consent', 'true');
    setIsVisible(false);
  };

  const handleDecline = () => {
    localStorage.setItem('cookie_consent', 'false');
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <div style={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 100, backgroundColor: '#0a0a0a', borderTop: '1px solid rgba(255,255,255,0.1)', padding: '1rem', boxShadow: '0 -10px 40px rgba(0,0,0,0.5)', fontSize: '0.9rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1rem' }} className="cookie-banner-inner">
        <style>{`
          @media (min-width: 768px) {
            .cookie-banner-inner { flex-direction: row !important; align-items: center; justify-content: space-between; }
          }
        `}</style>
        <div style={{ color: 'var(--text-muted, #9ca3af)' }}>
          <p style={{ margin: 0, lineHeight: 1.5 }}>
            We use cookies to improve your experience, analyze site traffic, and for marketing purposes. 
            By continuing to use this site, you consent to our use of cookies.
          </p>
          <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1rem', fontSize: '0.75rem', fontWeight: 500 }}>
            <a href="/privacy" style={{ color: '#6b7280', textDecoration: 'none' }} onMouseOver={e => e.target.style.color='#fff'} onMouseOut={e => e.target.style.color='#6b7280'}>Privacy Policy</a>
            <a href="/terms" style={{ color: '#6b7280', textDecoration: 'none' }} onMouseOver={e => e.target.style.color='#fff'} onMouseOut={e => e.target.style.color='#6b7280'}>Terms of Service</a>
            <a href="/dpa" style={{ color: '#6b7280', textDecoration: 'none' }} onMouseOver={e => e.target.style.color='#fff'} onMouseOut={e => e.target.style.color='#6b7280'}>Data Processing Agreement</a>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexShrink: 0 }}>
          <button 
            onClick={handleDecline}
            style={{ padding: '0.5rem 1rem', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', borderRadius: '4px', background: 'transparent', cursor: 'pointer', transition: '0.2s' }}
            onMouseOver={e => e.target.style.background='rgba(255,255,255,0.05)'} onMouseOut={e => e.target.style.background='transparent'}
          >
            Decline
          </button>
          <button 
            onClick={handleAccept}
            style={{ padding: '0.5rem 1rem', backgroundColor: '#fff', color: '#000', fontWeight: '600', borderRadius: '4px', border: 'none', cursor: 'pointer', boxShadow: '0 0 15px rgba(255,255,255,0.3)', transition: '0.2s' }}
            onMouseOver={e => e.target.style.backgroundColor='#e5e7eb'} onMouseOut={e => e.target.style.backgroundColor='#fff'}
          >
            Accept Cookies
          </button>
          <button onClick={handleDecline} style={{ background: 'transparent', border: 'none', color: '#6b7280', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '0.25rem', transition: '0.2s', borderRadius: '50%' }} onMouseOver={e => {e.currentTarget.style.color='#fff'; e.currentTarget.style.background='rgba(255,255,255,0.1)'}} onMouseOut={e => {e.currentTarget.style.color='#6b7280'; e.currentTarget.style.background='transparent'}}>
            <X size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
