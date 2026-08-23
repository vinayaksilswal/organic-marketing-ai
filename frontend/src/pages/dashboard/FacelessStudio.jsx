import React, { useCallback, useEffect, useState } from 'react';
import { Film, Sparkles, Copy, Check, RefreshCw } from 'lucide-react';
import { API_BASE, authFetch, apiError } from '../../config';
import { useWorkspace } from '../../components/WorkspaceContext';

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
