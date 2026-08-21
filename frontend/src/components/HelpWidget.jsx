import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { HelpCircle, X, MessageSquare, Book, LifeBuoy, Star, Sparkles } from 'lucide-react';

export default function HelpWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div style={{
      position: 'fixed',
      bottom: '1.5rem',
      right: '1.5rem',
      zIndex: 9999,
    }}>
      {isOpen && (
        <div style={{
          position: 'absolute',
          bottom: '3.75rem',
          right: 0,
          width: '320px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '16px',
          boxShadow: '0 20px 40px rgba(0,0,0,0.45)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          backdropFilter: 'blur(20px)',
          animation: 'fadeIn 0.2s ease-out',
        }}>
          <div style={{
            padding: '1rem 1.25rem',
            background: 'linear-gradient(135deg, rgba(109, 40, 217, 0.25), rgba(79, 70, 229, 0.15))',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-main)' }}>
              <LifeBuoy size={17} color="var(--primary-color)" /> Help &amp; Support
            </h3>
            <button
              onClick={() => setIsOpen(false)}
              aria-label="Close support menu"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '4px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <X size={17} />
            </button>
          </div>

          <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <button
              onClick={() => { setIsOpen(false); navigate('/dashboard/support'); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.75rem',
                background: 'rgba(11, 16, 32, 0.04)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(139, 92, 246, 0.08)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(11, 16, 32, 0.04)'; e.currentTarget.style.transform = 'none'; }}
            >
              <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(139, 92, 246, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <MessageSquare size={17} color="var(--primary-color)" />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 650, color: 'var(--text-main)' }}>Open Support Ticket</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Direct assistance &amp; bug reports</div>
              </div>
            </button>

            <button
              onClick={() => { setIsOpen(false); navigate('/dashboard/support'); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.75rem',
                background: 'rgba(11, 16, 32, 0.04)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(245, 158, 11, 0.08)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(11, 16, 32, 0.04)'; e.currentTarget.style.transform = 'none'; }}
            >
              <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(245, 158, 11, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Star size={17} color="#f59e0b" />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 650, color: 'var(--text-main)' }}>Platform Feedback &amp; Review</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Rate &amp; share your review</div>
              </div>
            </button>

            <button
              onClick={() => { setIsOpen(false); navigate('/dashboard/video-studio'); }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.75rem',
                background: 'rgba(11, 16, 32, 0.04)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(16, 185, 129, 0.08)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(11, 16, 32, 0.04)'; e.currentTarget.style.transform = 'none'; }}
            >
              <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(16, 185, 129, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Sparkles size={17} color="var(--success)" />
              </div>
              <div>
                <div style={{ fontSize: '0.88rem', fontWeight: 650, color: 'var(--text-main)' }}>AI Video Studio</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Generate 8s–30s video briefs</div>
              </div>
            </button>
          </div>

          <div style={{
            padding: '0.65rem 1rem',
            borderTop: '1px solid var(--border-color)',
            textAlign: 'center',
            fontSize: '0.74rem',
            color: 'var(--text-muted)',
            background: 'rgba(11, 16, 32, 0.02)',
          }}>
            Enterprise Support · 24/7 Available
          </div>
        </div>
      )}

      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Toggle support assistant"
        style={{
          width: '46px',
          height: '46px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--primary-color), #7c3aed)',
          color: 'var(--text-main)',
          border: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 8px 24px rgba(109, 40, 217, 0.45)',
          cursor: 'pointer',
          transition: 'transform 0.2s, box-shadow 0.2s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.08)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.transform = 'none'; }}
      >
        {isOpen ? <X size={20} /> : <HelpCircle size={22} />}
      </button>
    </div>
  );
}

