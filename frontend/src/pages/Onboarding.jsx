import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Building2, Globe, Target, CreditCard, CheckCircle2, ArrowRight, Loader2, Bot, Cpu, ImageIcon } from 'lucide-react';
import { API_BASE, authFetch } from '../config';

const Onboarding = ({ user, token, showToast, updateAuth }) => {
  const [step, setStep] = useState(1);
  const [website, setWebsite] = useState('');
  const [description, setDescription] = useState('');
  const [businessModel, setBusinessModel] = useState(null);
  const [niche, setNiche] = useState('');
  const [nicheOptions, setNicheOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // AI Analysis states
  const [analysisPhase, setAnalysisPhase] = useState(0); // 0=Extracting, 1=Brand Context, 2=Images
  // What the analysis actually produced. The final screen used to show a
  // hardcoded summary to every business under a heading claiming we had
  // analysed theirs.
  const [brand, setBrand] = useState(null);
  
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch niche options
    const fetchNiches = async () => {
      try {
        const res = await fetch(`${API_BASE}/niches`);
        if (res.ok) {
          const data = await res.json();
          if (data.success) setNicheOptions(data.niches);
        }
      } catch (err) {
        console.error('Failed to fetch niches', err);
      }
    };
    fetchNiches();

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
              if (data.profile) setBrand(data.profile);
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
    if (!niche) {
      showToast('Please select a niche', true);
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
          businessModel: businessModel,
          niche: niche
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
                { name: 'Faceless Channel', icon: '🎬' },
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

            <div className="input-group" style={{ marginTop: '2rem' }}>
              <label>Business Niche</label>
              <select value={niche} onChange={e => setNiche(e.target.value)} style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white', marginTop: '0.5rem' }}>
                <option value="">Select your niche...</option>
                {nicheOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>
                ))}
              </select>
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

            <h2 style={{ marginBottom: '2rem' }}>Organiflo is working...</h2>

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
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.75rem' }}>
              <CheckCircle2 size={30} color="var(--success)" />
              <h2 style={{ margin: 0 }}>{brand?.name || 'Your business'} is set up</h2>
            </div>
            <p style={{ marginBottom: '1.5rem', fontSize: '1.02rem', color: 'var(--text-muted)' }}>
              Here is what we learned from your site. Change anything you disagree with — this is what every caption and creative is written from.
            </p>

            {/* The real stored analysis, not a fixed string. */}
            <div style={{
              background: 'rgba(139, 92, 246, 0.06)', border: '1px solid rgba(139, 92, 246, 0.22)',
              borderRadius: 16, padding: '1.4rem', marginBottom: '1.25rem', textAlign: 'left',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.9rem', fontWeight: 700, color: 'var(--primary-color)' }}>
                <Sparkles size={17} /> What we understood
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginBottom: '1rem' }}>
                {brand?.industry && <span className="badge">{brand.industry}</span>}
                {brand?.toneOfVoice && <span className="badge">Tone: {brand.toneOfVoice}</span>}
                {brand?.businessModel && <span className="badge">{brand.businessModel}</span>}
                <span className="badge">Posts every {brand?.postIntervalHours ?? 2}h</span>
              </div>

              {brand?.primaryOffer && (
                <p style={{ margin: '0 0 0.7rem', fontSize: '0.88rem' }}>
                  <strong>Your call to action:</strong> {brand.primaryOffer}
                </p>
              )}
              {brand?.targetAudience && (
                <p style={{ margin: '0 0 0.7rem', fontSize: '0.88rem' }}>
                  <strong>Who you sell to:</strong> {brand.targetAudience}
                </p>
              )}
              {!!brand?.contentPillars?.length && (
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  <strong>Content pillars:</strong> {brand.contentPillars.join(' • ')}
                </p>
              )}
              {!brand && (
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Your brand profile is saved. Open Workspaces to review it.
                </p>
              )}
            </div>

            {/* What happens next, in the order it happens. Nothing here is
                gated: the free plan publishes, and asking for a card before a
                single post has gone out is asking someone to buy something
                they have not seen work. */}
            <div style={{ textAlign: 'left', marginBottom: '1.5rem' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>What happens next</h3>
              {[
                ['Connect Facebook and Instagram', 'One click each, in Workspaces. Nothing can publish until you do.'],
                ['Generate your first video prompt', 'Pick a length — the hook, the beats and the end card are written for it.'],
                ['Add your media', 'Upload clips or images. The scheduler posts from this library on your interval.'],
                ['It keeps posting', 'On your schedule, with every post reviewable before it goes out.'],
              ].map(([t, d], i) => (
                <div key={t} style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.85rem' }}>
                  <span style={{
                    flexShrink: 0, width: 26, height: 26, borderRadius: 99,
                    background: 'var(--primary-color)', color: '#fff', fontWeight: 700,
                    fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  }}>{i + 1}</span>
                  <span>
                    <span style={{ display: 'block', fontWeight: 650, fontSize: '0.92rem' }}>{t}</span>
                    <span style={{ display: 'block', fontSize: '0.83rem', color: 'var(--text-muted)' }}>{d}</span>
                  </span>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              <button
                className="btn btn-primary btn-large"
                style={{ width: '100%', minHeight: 48, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                onClick={() => navigate('/dashboard/video-studio')}
              >
                <Sparkles size={18} /> Generate Your First AI Video <ArrowRight size={17} />
              </button>
              <button
                className="btn btn-secondary"
                style={{ width: '100%', minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                onClick={() => navigate('/dashboard/workspaces')}
              >
                <Building2 size={16} /> Connect Social Accounts (Meta / TikTok)
              </button>
              <button
                className="btn"
                style={{ width: '100%', minHeight: 38, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.85rem' }}
                onClick={() => navigate('/dashboard')}
              >
                Skip to Dashboard
              </button>
            </div>
            <p style={{ marginTop: '1rem', fontSize: '0.83rem', color: 'var(--text-muted)' }}>
              Brand intelligence active · Autonomous marketing ready to scale
            </p>
          </div>
        )}

      </div>
    </div>
  );
};

export default Onboarding;
