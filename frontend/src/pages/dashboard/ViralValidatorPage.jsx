import React from 'react';
import { Flame, Eye, Sparkles, TrendingUp } from 'lucide-react';
import ViralValidator from '../../components/ViralValidator';
import { useWorkspace } from '../../components/WorkspaceContext';

export default function ViralValidatorPage({ user, token, showToast, activeWorkspaceId }) {
  const { activeWorkspace } = useWorkspace();
  const businessName = activeWorkspace?.name || 'Active Business';

  return (
    <div className="view">
      <div className="container" style={{ padding: '2.5rem 0', maxWidth: 1080 }}>
        
        {/* Top Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '2rem',
          flexWrap: 'wrap',
          gap: '1rem',
          background: 'linear-gradient(135deg, rgba(249, 115, 22, 0.08) 0%, rgba(234, 88, 12, 0.03) 100%)',
          padding: '1.5rem 2rem',
          borderRadius: '14px',
          border: '1px solid rgba(249, 115, 22, 0.25)',
        }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.2rem 0.65rem', borderRadius: 16, background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.3)', marginBottom: '0.5rem' }}>
              <Flame size={13} color="#f97316" />
              <span style={{ fontSize: '0.72rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.06em', color: '#f97316' }}>
                Core Platform AI Engine
              </span>
            </div>
            <h1 style={{ margin: 0, fontSize: '1.85rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
              Viral Validator &amp; View Predictor
            </h1>
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
              Test your short-form video hooks, scripts &amp; reels against the 5-axis algorithmic simulation for <strong style={{ color: 'var(--text-main)' }}>{businessName}</strong>.
            </p>
          </div>
        </div>

        {/* Viral Validator Interactive Component */}
        <ViralValidator
          token={token}
          showToast={showToast}
          activeWorkspaceId={activeWorkspaceId}
        />

        {/* Value Pillars */}
        <div style={{ marginTop: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
          <div style={{ background: 'rgba(11,16,32,0.03)', borderRadius: 14, padding: '1.25rem', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <Eye size={18} color="#f97316" />
              <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>Stop Posting Blindly</h4>
            </div>
            <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Know exactly how your video will perform before you hit upload. Algorithmic prediction simulates 500M+ viral shorts.
            </p>
          </div>

          <div style={{ background: 'rgba(11,16,32,0.03)', borderRadius: 14, padding: '1.25rem', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <Sparkles size={18} color="#f97316" />
              <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>Timestamped Fix The Fail</h4>
            </div>
            <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Get precise algorithmic corrections: "Cut intro at 0:02", "Add visual zoom at 0:04", "Include polarizing CTA".
            </p>
          </div>

          <div style={{ background: 'rgba(11,16,32,0.03)', borderRadius: 14, padding: '1.25rem', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <TrendingUp size={18} color="#f97316" />
              <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 800, color: '#fff' }}>10x Organic Velocity</h4>
            </div>
            <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Consistent high stop-rate hooks and watch time retention turn organic shorts into a predictable customer acquisition flywheel.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
}
