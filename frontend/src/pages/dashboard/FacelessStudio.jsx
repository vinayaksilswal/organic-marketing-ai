import React, { useCallback, useEffect, useState } from 'react';
import { Film, Sparkles, Copy, Check, RefreshCw, Clock, Zap, Settings, CheckCircle2 } from 'lucide-react';
import { API_BASE, authFetch, apiError } from '../../config';
import { useWorkspace } from '../../components/WorkspaceContext';
import MediaProviderConnect from '../../components/MediaProviderConnect';

/**
 * Faceless Shorts.
 *
 * The service, its presets, its quota metering and its tests have existed for
 * a while, and the landing page sells the feature by name — but nothing in the
 * interface ever called the endpoints. A customer who picked "Faceless
 * Channel" as their business model got dedicated settings in Workspaces and no
 * way to generate anything.
 *
 * This is that missing half. The layout deliberately matches Brand Video
 * Studio: same panel, same controls, same three-prompt output, because they do
 * the same job and looking different would only imply they do not.
 */
export default function FacelessStudio({ token, activeWorkspaceId, showToast }) {
  const { activeWorkspace, workspaces } = useWorkspace();
  const workspace = activeWorkspace || workspaces?.find((w) => w.id === activeWorkspaceId) || null;
  const channelName = workspace?.name || 'your channel';

  const [presets, setPresets] = useState(null);
  const [topicId, setTopicId] = useState('scary_stories');
  const [customTopic, setCustomTopic] = useState('');
  const [styleId, setStyleId] = useState('cinematic_realism');
  const [voiceId, setVoiceId] = useState('adam_storyteller');
  const [duration, setDuration] = useState(20);

  // Auto-Pilot State
  const [schedulePreset, setSchedulePreset] = useState('daily');
  const [publishingMode, setPublishingMode] = useState('PUBLIC');
  const [autoApprove, setAutoApprove] = useState(false);
  const [savingAutopilot, setSavingAutopilot] = useState(false);
  const [autopilotConfigured, setAutopilotConfigured] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState('');

  const loadPresets = useCallback(async () => {
    try {
      const res = await authFetch(`${API_BASE}/creatives/faceless-presets`, {}, token);
      if (res.ok) setPresets(await res.json());
    } catch {
      /* The form still works on its defaults; presets only widen the choice. */
    }
  }, [token]);

  useEffect(() => { loadPresets(); }, [loadPresets]);

  const saveAutopilot = async () => {
    if (!activeWorkspaceId) {
      showToast?.('Please select a workspace first.', true);
      return;
    }
    setSavingAutopilot(true);
    try {
      const res = await authFetch(`${API_BASE}/creatives/faceless-autopilot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          schedule_preset: schedulePreset,
          publishing_mode: publishingMode,
          auto_approve: autoApprove,
        }),
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiError(body, 'Could not save autopilot settings.'));
      setAutopilotConfigured(true);
      showToast?.('Auto-Pilot channel schedule activated! 🚀');
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      setSavingAutopilot(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    setResult(null);
    try {
      const res = await authFetch(`${API_BASE}/creatives/faceless-generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({
          topic_id: topicId,
          custom_topic: topicId === 'custom' ? customTopic : null,
          visual_style_id: styleId,
          voice_id: voiceId,
          duration_seconds: Number(duration),
          channel_name: channelName,
        }),
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiError(body, 'Could not generate that short.'));
      setResult(body.short || body);
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      setGenerating(false);
    }
  };

  const copy = (text, key) => {
    navigator.clipboard?.writeText(text || '');
    setCopied(key);
    setTimeout(() => setCopied(''), 1600);
  };

  const topics = presets?.topics || [];
  const styles = presets?.visual_styles || [];
  const voices = presets?.voice_personas || [];

  const label = {
    fontSize: '0.76rem', fontWeight: 800, color: 'var(--text-muted)',
    textTransform: 'uppercase', marginBottom: '0.4rem', display: 'block',
  };
  const field = {
    width: '100%', padding: '0.6rem 0.7rem', borderRadius: 10,
    border: '1px solid var(--border-color)', background: 'rgba(11,16,32,0.03)',
    color: 'var(--text-main)', fontSize: '0.88rem', minHeight: 44,
  };

  const PromptCard = ({ title, body, tone, tools, k }) => (
    <div style={{
      background: 'var(--bg-card)', borderRadius: 14, padding: '1.25rem',
      border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.7rem' }}>
        <span style={{ fontSize: '0.74rem', fontWeight: 800, color: tone, textTransform: 'uppercase', letterSpacing: '.04em' }}>
          {title}
        </span>
        <button
          onClick={() => copy(body, k)}
          className="btn btn-secondary"
          style={{ minHeight: 34, fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
        >
          {copied === k ? <Check size={13} /> : <Copy size={13} />} {copied === k ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre style={{
        margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', flex: 1,
        fontSize: '0.78rem', lineHeight: 1.6, color: 'var(--text-main)',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        background: 'rgba(11,16,32,0.03)', borderRadius: 10, padding: '0.85rem',
      }}>{body || '—'}</pre>
      {tools && (
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.6rem' }}>{tools}</div>
      )}
    </div>
  );

  return (
    <div className="container" style={{ padding: '2.5rem 0' }}>
      <div style={{
        background: 'linear-gradient(135deg, rgba(109, 40, 217, 0.08) 0%, rgba(91, 33, 182, 0.03) 100%)',
        borderRadius: 16, padding: '1.75rem', border: '1px solid rgba(109, 40, 217, 0.25)',
        marginBottom: '2rem',
      }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.2rem 0.65rem',
          borderRadius: 16, background: 'rgba(109, 40, 217, 0.12)', border: '1px solid rgba(109, 40, 217, 0.3)',
          marginBottom: '0.5rem', fontSize: '0.72rem', fontWeight: 800,
          textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--primary-color)',
        }}>
          <Film size={13} /> Faceless Shorts
        </span>
        <h1 style={{ margin: 0, fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
          Faceless Short Videos
        </h1>
        <p style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          A hook, a voiceover script, both keyframe prompts and a caption — written for{' '}
          <strong style={{ color: 'var(--text-main)' }}>{channelName}</strong>. Nobody has to be on camera.
        </p>
      </div>

      <div style={{ padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 14, border: '1px solid var(--border-color)', marginBottom: '2rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.25rem', marginBottom: '1.25rem' }}>
          <div>
            <label style={label}>Topic</label>
            <select value={topicId} onChange={(e) => setTopicId(e.target.value)} style={field}>
              {topics.length === 0 && <option value="scary_stories">Scary stories</option>}
              {topics.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
              <option value="custom">Something else…</option>
            </select>
          </div>

          <div>
            <label style={label}>Visual style</label>
            <select value={styleId} onChange={(e) => setStyleId(e.target.value)} style={field}>
              {styles.length === 0 && <option value="cinematic_realism">Cinematic realism</option>}
              {styles.map((v) => <option key={v.id} value={v.id}>{v.title || v.name || v.id}</option>)}
            </select>
          </div>

          <div>
            <label style={label}>Voice</label>
            <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} style={field}>
              {voices.length === 0 && <option value="adam_storyteller">Storyteller</option>}
              {voices.map((v) => <option key={v.id} value={v.id}>{v.title || v.name || v.id}</option>)}
            </select>
          </div>

          <div>
            <label style={label}>Length</label>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {[15, 20, 30, 45, 60].map((sec) => (
                <button
                  key={sec}
                  onClick={() => setDuration(sec)}
                  style={{
                    flex: 1, minWidth: 54, minHeight: 44, borderRadius: 10, cursor: 'pointer',
                    fontWeight: 700, fontSize: '0.82rem',
                    background: duration === sec ? 'var(--primary-color)' : 'rgba(11, 16, 32, 0.04)',
                    color: duration === sec ? '#fff' : 'var(--text-main)',
                    border: `1px solid ${duration === sec ? 'var(--primary-color)' : 'var(--border-color)'}`,
                  }}
                >
                  {sec}s
                </button>
              ))}
            </div>
          </div>
        </div>

        {topicId === 'custom' && (
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={label}>What should it be about?</label>
            <input
              value={customTopic}
              onChange={(e) => setCustomTopic(e.target.value)}
              placeholder="e.g. Dark Greek mythology and Medusa's curse"
              style={field}
            />
          </div>
        )}

        {/* Shorts are rendered on the customer's own account, so the connect
            control belongs beside the button that needs it rather than buried
            in a settings page they would never find.

            The prompts are passed in so the Generate button can appear the
            moment there is something to render -- before that, `result` is
            null, the prompt is undefined and only the connect control shows. */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <MediaProviderConnect
            kind="video"
            token={token}
            activeWorkspaceId={activeWorkspaceId}
            showToast={showToast}
            prompt={result?.video_prompt}
          />
          <MediaProviderConnect
            kind="image"
            token={token}
            activeWorkspaceId={activeWorkspaceId}
            showToast={showToast}
            prompt={result?.first_frame_prompt}
          />
        </div>

        <button
          onClick={generate}
          disabled={generating || (topicId === 'custom' && !customTopic.trim())}
          className="btn btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', minHeight: 46, fontWeight: 700 }}
        >
          {generating ? <RefreshCw size={16} className="spin" /> : <Sparkles size={16} />}
          {generating ? 'Writing the short…' : 'Generate the short'}
        </button>
      </div>

      {/* Auto-Pilot Channel Schedule Panel */}
      <div style={{
        padding: '1.5rem',
        background: 'var(--bg-card)',
        borderRadius: 14,
        border: '1px solid var(--border-color)',
        marginBottom: '2rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.25rem' }}>
              <Zap size={16} color="var(--primary-color)" />
              <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800 }}>Auto-Pilot Channel Posting</h2>
            </div>
            <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--text-muted)' }}>
              Automatically generate and schedule viral shorts to your social queue on a recurring cadence.
            </p>
          </div>
          {autopilotConfigured && (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.25rem 0.65rem',
              borderRadius: 12,
              background: 'rgba(16, 185, 129, 0.1)',
              color: 'var(--success)',
              fontSize: '0.75rem',
              fontWeight: 700,
            }}>
              <CheckCircle2 size={13} /> Active
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <label style={label}>Posting Cadence</label>
            <select
              value={schedulePreset}
              onChange={(e) => setSchedulePreset(e.target.value)}
              style={field}
            >
              <option value="daily">Daily (7 posts / week)</option>
              <option value="weekdays">Weekdays (Mon - Fri, 5 posts / wk)</option>
              <option value="three_per_week">3x per week (Mon, Wed, Fri)</option>
              <option value="twice_daily">2x Daily (High Growth, 14 posts / wk)</option>
            </select>
          </div>

          <div>
            <label style={label}>Publishing Visibility</label>
            <select
              value={publishingMode}
              onChange={(e) => setPublishingMode(e.target.value)}
              style={field}
            >
              <option value="PUBLIC">Direct to Queue (Auto-Publish)</option>
              <option value="DRAFT">Save as Draft (Review First)</option>
            </select>
          </div>

          <div>
            <label style={label}>Auto-Approve Creatives</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', minHeight: 44 }}>
              <input
                type="checkbox"
                id="autoApproveCheck"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
                style={{ width: 18, height: 18, cursor: 'pointer', accentColor: 'var(--primary-color)' }}
              />
              <label htmlFor="autoApproveCheck" style={{ fontSize: '0.84rem', color: 'var(--text-main)', cursor: 'pointer' }}>
                Auto-approve queued shorts
              </label>
            </div>
          </div>
        </div>

        <button
          onClick={saveAutopilot}
          disabled={savingAutopilot}
          className="btn btn-secondary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', minHeight: 40, fontWeight: 700, fontSize: '0.84rem' }}
        >
          {savingAutopilot ? <RefreshCw size={14} className="spin" /> : <Clock size={14} />}
          {savingAutopilot ? 'Activating Auto-Pilot…' : 'Save Auto-Pilot Schedule'}
        </button>
      </div>

      {result && (
        <>
          <div style={{ padding: '1.5rem', background: 'var(--bg-card)', borderRadius: 14, border: '1px solid var(--border-color)', marginBottom: '1.5rem' }}>
            <h2 style={{ margin: '0 0 0.5rem', fontSize: '1.15rem' }}>{result.title}</h2>
            <p style={{ margin: 0, fontSize: '0.92rem', fontWeight: 600, color: 'var(--primary-color)', lineHeight: 1.5 }}>
              {result.hook}
            </p>
            <div style={{ marginTop: '1rem' }}>
              <span style={{ ...label, marginBottom: '0.3rem' }}>Voiceover script</span>
              <p style={{ margin: 0, fontSize: '0.88rem', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {result.voiceover_script}
              </p>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
            <PromptCard k="first" title="Opening frame" tone="var(--secondary-color)"
              body={result.first_frame_prompt} tools="Midjourney / Flux / Ideogram" />
            <PromptCard k="video" title="Motion prompt" tone="var(--primary-color)"
              body={result.video_prompt} tools="Kling / Runway / Veo / Sora" />
            <PromptCard k="last" title="Closing card" tone="var(--success)"
              body={result.last_frame_prompt} tools="Midjourney / Flux / Ideogram" />
          </div>

          <PromptCard k="caption" title="Caption" tone="var(--accent-color)" body={result.viral_caption} />
        </>
      )}
    </div>
  );
}
