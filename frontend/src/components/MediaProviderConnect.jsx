import React, { useCallback, useEffect, useState } from 'react';
import { Plug, Check, X, Loader2 } from 'lucide-react';
import { API_BASE, authFetch, apiError } from '../config';

/**
 * Connect your own rendering account.
 *
 * The studios write prompts. Turning a prompt into a file costs money at
 * Runway or Replicate, so the workspace brings its own key and picks its own
 * model rather than metering through a shared account.
 *
 * The key leaves the browser once and never comes back. What returns is a
 * masked hint — enough to recognise which key is connected, useless to
 * anybody who reads it out of a log. So the input is left empty when a
 * connection already exists: showing dots that are not the real key invites
 * somebody to "save" them.
 *
 * `kind` is 'image' or 'video'. One of these sits on each prompt generator.
 */
export default function MediaProviderConnect({ kind, token, activeWorkspaceId, showToast }) {
  const [open, setOpen] = useState(false);
  const [catalogue, setCatalogue] = useState([]);
  const [current, setCurrent] = useState({ connected: false });
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!activeWorkspaceId) return;
    try {
      const res = await authFetch(`${API_BASE}/creatives/media-providers`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) return;
      const list = body.providers?.[kind] || [];
      setCatalogue(list);
      const mine = body.connected?.[kind] || { connected: false };
      setCurrent(mine);
      // Preselect what is already connected, so opening the panel to change
      // the model does not silently reset the provider too.
      setProvider(mine.provider || list[0]?.id || '');
      setModel(mine.model || list[0]?.models?.[0] || '');
    } catch {
      /* The studio still works without this; a failed probe is not worth a toast. */
    }
  }, [activeWorkspaceId, token, kind]);

  useEffect(() => { load(); }, [load]);

  const entry = catalogue.find((p) => p.id === provider);

  const pickProvider = (id) => {
    setProvider(id);
    const next = catalogue.find((p) => p.id === id);
    setModel(next?.models?.[0] || '');
  };

  const save = async () => {
    if (!apiKey.trim()) {
      showToast?.('Paste the API key first.', true);
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch(`${API_BASE}/creatives/media-providers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({ kind, provider, model, apiKey: apiKey.trim() }),
      }, token);
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(apiError(body, 'Could not save that key.'));
      setApiKey('');
      setOpen(false);
      await load();
      showToast?.(`${entry?.name || provider} connected.`);
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await authFetch(`${API_BASE}/creatives/media-providers/${kind}`, {
        method: 'DELETE',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      await load();
      showToast?.('Disconnected.');
    } catch (err) {
      showToast?.(err.message, true);
    } finally {
      setBusy(false);
    }
  };

  const label = kind === 'image' ? 'image' : 'video';

  return (
    <div style={{ marginBottom: '1rem' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="btn btn-secondary"
        style={{
          minHeight: 40, fontSize: '0.8rem', fontWeight: 700,
          display: 'inline-flex', alignItems: 'center', gap: '0.45rem',
        }}
      >
        {current.connected
          ? <Check size={14} style={{ color: 'var(--success)' }} />
          : <Plug size={14} />}
        {current.connected
          ? `${entry?.name || current.provider} connected`
          : `Connect your ${label} API`}
      </button>

      {current.connected && !open && (
        <span style={{ marginLeft: '0.6rem', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
          {current.model || 'default model'} · key {current.keyHint}
        </span>
      )}

      {open && (
        <div style={{
          marginTop: '0.75rem', padding: '1rem', borderRadius: 12,
          border: '1px solid var(--border-color)', background: 'rgba(11,16,32,0.02)',
          display: 'grid', gap: '0.75rem', maxWidth: 460,
        }}>
          <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
            Renders run on your own account, so you keep the credits and the
            output. The key is encrypted here and never shown again.
          </p>

          <div>
            <label style={{
              fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-muted)',
              textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem',
            }}>Provider</label>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {catalogue.map((p) => (
                <button
                  key={p.id}
                  onClick={() => pickProvider(p.id)}
                  style={{
                    minHeight: 38, padding: '0 0.75rem', borderRadius: 9, cursor: 'pointer',
                    fontSize: '0.8rem', fontWeight: 700,
                    background: provider === p.id ? 'var(--primary-color)' : 'transparent',
                    color: provider === p.id ? '#fff' : 'var(--text-main)',
                    border: `1px solid ${provider === p.id ? 'var(--primary-color)' : 'var(--border-color)'}`,
                  }}
                >
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          {entry?.models?.length > 0 && (
            <div>
              <label style={{
                fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-muted)',
                textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem',
              }}>Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={{
                  width: '100%', minHeight: 42, borderRadius: 9, padding: '0 0.6rem',
                  border: '1px solid var(--border-color)', background: 'var(--bg-card)',
                  color: 'var(--text-main)', fontSize: '0.84rem',
                }}
              >
                {entry.models.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
          )}

          <div>
            <label style={{
              fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-muted)',
              textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem',
            }}>API key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={current.connected ? 'Paste a new key to replace it' : 'Paste your key'}
              style={{
                width: '100%', minHeight: 42, borderRadius: 9, padding: '0 0.6rem',
                border: '1px solid var(--border-color)', background: 'var(--bg-card)',
                color: 'var(--text-main)', fontSize: '0.84rem',
              }}
            />
            {entry?.keyHint && (
              <p style={{ margin: '0.35rem 0 0', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                {entry.keyHint}
              </p>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              onClick={save}
              disabled={busy}
              className="btn btn-primary"
              style={{ minHeight: 40, fontSize: '0.82rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
            >
              {busy ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
              {current.connected ? 'Replace key' : 'Connect'}
            </button>
            {current.connected && (
              <button
                onClick={remove}
                disabled={busy}
                className="btn btn-secondary"
                style={{ minHeight: 40, fontSize: '0.82rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
              >
                <X size={14} /> Disconnect
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
