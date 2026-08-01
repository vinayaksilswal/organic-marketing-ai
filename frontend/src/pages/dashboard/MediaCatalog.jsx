import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../config';
import { Upload, Trash2, Edit, Play, Eye, X, Sparkles, Copy, AlertTriangle, RefreshCw } from 'lucide-react';

const MediaCatalog = ({ user, token, showToast, activeWorkspaceId }) => {
  const [mediaList, setMediaList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [baseCaption, setBaseCaption] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [bulkFiles, setBulkFiles] = useState([]);
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkProgress, setBulkProgress] = useState('');
  const [bulkResult, setBulkResult] = useState(null);
  const [autoCaption, setAutoCaption] = useState(true);
  
  // Modals
  const [previewMedia, setPreviewMedia] = useState(null);
  const [editingMedia, setEditingMedia] = useState(null);
  const [editCaption, setEditCaption] = useState('');
  const [editFile, setEditFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMedia();
  }, [activeWorkspaceId]);

  const fetchMedia = async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media`, {}, token);
      if (res.ok) {
        setMediaList(await res.json());
        setLoadError(null);
      } else {
        // Never let a failed request masquerade as "you have no media" — that
        // sends users hunting for an upload that actually succeeded.
        setLoadError(
          res.status >= 500
            ? 'The server could not return your media (error ' + res.status + '). Your uploads are safe — this is a server-side fault.'
            : 'Could not load your media (error ' + res.status + ').'
        );
      }
    } catch (err) {
      console.error('Failed to fetch media', err);
      setLoadError('Could not reach the server to load your media.');
    } finally {
      setLoading(false);
    }
  };

  // Sent in batches rather than one 242-file request: a single upload of a
  // whole library exceeds request size limits and gives no progress, and one
  // network blip loses the lot. Each batch is independent.
  //
  // Three, not eight. Each video is uploaded to storage and has its end card
  // composited, and the server is killed at a 120s request timeout — eight
  // videos could not finish, so every batch returned 500.
  const BULK_BATCH = 3;

  const handleBulkUpload = async () => {
    if (!bulkFiles.length) return;
    setBulkUploading(true);
    setBulkResult(null);

    const media = bulkFiles.filter(f =>
      f.type.startsWith('image/') || f.type.startsWith('video/'));
    if (!media.length) {
      setBulkResult({ message: 'That folder had no images or videos in it.', failed: 0 });
      setBulkUploading(false);
      return;
    }

    let stored = 0, failed = 0, described = 0;
    try {
      for (let i = 0; i < media.length; i += BULK_BATCH) {
        const batch = media.slice(i, i + BULK_BATCH);
        setBulkProgress(`${Math.min(i + batch.length, media.length)} / ${media.length}`);

        const form = new FormData();
        batch.forEach(f => form.append('files', f));
        form.append('write_captions', autoCaption ? 'true' : 'false');

        try {
          const res = await authFetch(
            `${API_BASE}/marketing/media/bulk-upload`,
            { method: 'POST', body: form },
            token
          );
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const d = await res.json();
          stored += d.stored || 0;
          failed += d.failed || 0;
          described += d.described || 0;
        } catch (err) {
          // One failed batch must not abandon the rest of the folder.
          failed += batch.length;
          console.error('bulk batch failed', err);
        }
      }

      setBulkResult({
        message: `${stored} of ${media.length} added` +
                 (described ? `, ${described} described automatically` : ''),
        failed,
      });
      setBulkFiles([]);
      await fetchMedia();
    } finally {
      setBulkUploading(false);
      setBulkProgress('');
    }
  };

  const handleFileUploadAndCreate = async () => {
    if (!selectedFile) return showToast('Please select a file to upload', true);
    
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (baseCaption) {
         formData.append('caption', baseCaption);
      }

      const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
      const res = await fetch(`${API_BASE}/upload-media`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          ...(activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {})
        },
        body: formData
      });

      if (!res.ok) throw new Error('Upload failed');
      
      showToast('Campaign created successfully!');
      setBaseCaption('');
      setSelectedFile(null);
      // reset file input
      const fileInput = document.getElementById('campaign-file-upload');
      if(fileInput) fileInput.value = '';
      fetchMedia();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteMedia = async (id) => {
    if (!window.confirm('Delete this campaign?')) return;
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/${id}`, {
        method: 'DELETE'
      }, token);
      if (res.ok) {
        showToast('Campaign deleted!');
        fetchMedia();
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };
  
  const handleEditMedia = (item) => {
    setEditingMedia(item);
    // Fall back to the generation prompt, never the filename — the filename is
    // not a description and feeding it to the caption writer taught it nothing.
    setEditCaption(item.caption || item.prompt || '');
    setEditFile(null);
  };

  const handleSaveEdit = async () => {
    if (!editingMedia) return;
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('caption', editCaption);
      if (editFile) formData.append('file', editFile);

      const res = await authFetch(`${API_BASE}/marketing/media/${editingMedia.id}`, {
        method: 'PATCH',
        body: formData,
      }, token);

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Save failed (error ${res.status})`);
      }

      showToast(editFile ? 'Caption and media updated' : 'Base caption updated');
      setEditingMedia(null);
      setEditFile(null);
      await fetchMedia();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (item) => {
    try {
      const formData = new FormData();
      formData.append('isActive', item.isActive === false ? 'true' : 'false');

      const res = await authFetch(`${API_BASE}/marketing/media/${item.id}`, {
        method: 'PATCH',
        body: formData,
      }, token);

      if (!res.ok) throw new Error(`Could not update (error ${res.status})`);

      showToast(item.isActive === false
        ? 'Asset reactivated — automation can post it again'
        : 'Asset deactivated — automation will skip it');
      await fetchMedia();
    } catch (err) {
      showToast(err.message, true);
    }
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        
        {/* HEADER */}
        <h2 style={{ 
          margin: '0 0 2rem 0', 
          fontSize: '1.25rem', 
          textTransform: 'uppercase', 
          letterSpacing: '1px',
          borderBottom: '2px solid var(--primary-color)',
          display: 'inline-block',
          paddingBottom: '0.25rem'
        }}>
          CAMPAIGN MANAGEMENT
        </h2>

        {/* UPLOAD SECTION */}
        <div className="glass-panel" style={{ padding: '2rem', marginBottom: '2rem', display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: '1.5rem', alignItems: 'end' }}>
          
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Upload Image/Video for AI Campaign
            </label>
            <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem', height: '42px' }}>
              <input 
                type="file" 
                id="campaign-file-upload"
                onChange={(e) => setSelectedFile(e.target.files[0])} 
                style={{ fontSize: '0.85rem', width: '100%', color: 'var(--text-muted)' }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Base Caption — describe what the file shows
            </label>
            <input
              type="text"
              className="input"
              placeholder="e.g. Founder demos the scanner on a laptop in a dark office"
              value={baseCaption}
              onChange={(e) => setBaseCaption(e.target.value)}
              style={{ width: '100%', padding: '0.6rem 1rem', height: '42px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', color: '#fff', borderRadius: '8px' }}
            />
          </div>

          <button 
            className="btn btn-primary" 
            onClick={handleFileUploadAndCreate} 
            disabled={uploading}
            style={{ height: '42px', padding: '0 1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {uploading ? <span className="spinner"></span> : <><Upload size={16} /> UPLOAD & CREATE</>}
          </button>
        </div>

        {/* Bulk folder ingest. A single-file form is unusable for a real
            content library — this account arrived with 242 clips — and typing
            a base caption 242 times is worse. The vision model writes each
            one from a frame of the actual asset. */}
        <div className="glass-panel" style={{ marginBottom: '1.5rem', padding: '1.25rem 1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Or add a whole folder
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem' }}>
            <input
              type="file"
              id="bulk-folder-upload"
              multiple
              webkitdirectory=""
              directory=""
              onChange={(e) => setBulkFiles(Array.from(e.target.files || []))}
              style={{ display: 'none' }}
            />
            <button className="btn btn-secondary" style={{ height: 42 }}
              onClick={() => document.getElementById('bulk-folder-upload').click()}
              disabled={bulkUploading}>
              Choose folder
            </button>

            <input
              type="file"
              id="bulk-files-upload"
              multiple
              onChange={(e) => setBulkFiles(Array.from(e.target.files || []))}
              style={{ display: 'none' }}
            />
            <button className="btn btn-secondary" style={{ height: 42 }}
              onClick={() => document.getElementById('bulk-files-upload').click()}
              disabled={bulkUploading}>
              Choose files
            </button>

            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              <input type="checkbox" checked={autoCaption}
                onChange={(e) => setAutoCaption(e.target.checked)} />
              Write base captions with AI
            </label>

            {bulkFiles.length > 0 && (
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {bulkFiles.length} file{bulkFiles.length === 1 ? '' : 's'} selected
              </span>
            )}

            <button className="btn btn-primary" style={{ height: 42, marginLeft: 'auto' }}
              onClick={handleBulkUpload}
              disabled={bulkUploading || bulkFiles.length === 0}>
              {bulkUploading
                ? <><span className="spinner"></span> {bulkProgress || 'Uploading...'}</>
                : <><Upload size={16} /> UPLOAD {bulkFiles.length || ''}</>}
            </button>
          </div>
          {bulkResult && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: bulkResult.failed ? 'var(--warning, #e0a800)' : 'var(--text-muted)' }}>
              {bulkResult.message}
              {bulkResult.failed > 0 && ` — ${bulkResult.failed} skipped`}
            </p>
          )}
        </div>

        {/* TABLE SECTION */}
        <div className="glass-panel" style={{ overflowX: 'auto', border: 'none', background: 'transparent', boxShadow: 'none' }}>
          <div className="glass-panel" style={{ overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '1rem 1.5rem', fontWeight: '600' }}>Media</th>
                  <th style={{ padding: '1rem 1.5rem', fontWeight: '600' }}>Base Caption</th>
                  <th style={{ padding: '1rem 1.5rem', fontWeight: '600' }}>Status</th>
                  <th style={{ padding: '1rem 1.5rem', fontWeight: '600' }}>Created</th>
                  <th style={{ padding: '1rem 1.5rem', fontWeight: '600', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="5" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      <span className="spinner" style={{ width: 20, height: 20 }} />
                    </td>
                  </tr>
                ) : loadError ? (
                  <tr>
                    <td colSpan="5" style={{ padding: '2.5rem', textAlign: 'center' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                        <AlertTriangle size={22} color="#f87171" />
                        <div style={{ color: '#fca5a5', fontSize: '0.9rem', maxWidth: 460, lineHeight: 1.55 }}>
                          {loadError}
                        </div>
                        <button className="btn btn-secondary" onClick={fetchMedia}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.45rem 0.9rem', fontSize: '0.83rem' }}>
                          <RefreshCw size={14} /> Retry
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : mediaList.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No media yet. Upload a file above, or generate one in AI Video Studio.
                    </td>
                  </tr>
                ) : (
                  mediaList.map(item => {
                    const isVideo = item.mimeType?.startsWith('video/') || item.filename?.endsWith('.mp4');
                    const caption = item.caption || item.prompt || '';
                    const inactive = item.isActive === false;
                    return (
                      <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '1rem 1.5rem', width: '80px' }}>
                          <div style={{ width: '56px', height: '56px', borderRadius: '8px', overflow: 'hidden', background: '#000', position: 'relative' }}>
                            {isVideo ? (
                              <video src={item.url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (
                              <img src={item.url} alt="media" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            )}
                          </div>
                        </td>
                        <td style={{ padding: '1rem 1.5rem', maxWidth: '340px' }}>
                          {caption ? (
                            <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                              {caption}
                            </p>
                          ) : (
                            <p style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.4, color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                              <AlertTriangle size={13} />
                              No description — the AI cannot see this asset. Add one via Edit.
                            </p>
                          )}
                          <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            {item.filename}
                          </p>
                          {item.prompt && (
                            <details style={{ marginTop: '0.5rem' }}>
                              <summary style={{ cursor: 'pointer', fontSize: '0.72rem', color: 'var(--primary-color)', display: 'flex', alignItems: 'center', gap: '0.3rem', listStyle: 'none' }}>
                                <Sparkles size={11} />
                                {item.promptType === 'video' ? 'Video prompt' : 'AI prompt'}
                              </summary>
                              <div style={{ marginTop: '0.5rem', padding: '0.6rem 0.7rem', borderRadius: '7px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.06)' }}>
                                <p style={{ margin: 0, fontSize: '0.75rem', lineHeight: 1.55, color: '#d4d4d8', fontStyle: 'italic', whiteSpace: 'pre-wrap' }}>
                                  {item.prompt}
                                </p>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(item.prompt);
                                    showToast('Prompt copied to clipboard');
                                  }}
                                  style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.3rem', background: 'none', border: 'none', color: 'var(--primary-color)', fontSize: '0.72rem', cursor: 'pointer', padding: 0, fontWeight: 600 }}
                                >
                                  <Copy size={11} /> Copy prompt
                                </button>
                              </div>
                            </details>
                          )}
                        </td>
                        <td style={{ padding: '1rem 1.5rem' }}>
                          {/* Reflects the real isActive column and whether the
                              asset is something automation can actually post.
                              This used to be a hardcoded ACTIVE badge. */}
                          <span style={{
                            fontSize: '0.75rem', fontWeight: '700', padding: '0.2rem 0.6rem',
                            borderRadius: '4px',
                            background: inactive ? 'rgba(148,163,184,0.15)'
                              : item.postable === false ? 'rgba(251,191,36,0.15)'
                              : 'rgba(16,185,129,0.15)',
                            color: inactive ? '#94a3b8'
                              : item.postable === false ? '#fbbf24'
                              : 'var(--success)',
                          }}>
                            {inactive ? 'PAUSED' : item.postable === false ? 'PROMPT ONLY' : 'ACTIVE'}
                          </span>
                          {item.postable === false && !inactive && (
                            <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.68rem', color: 'var(--text-muted)', maxWidth: 150, lineHeight: 1.4 }}>
                              A saved prompt, not a file. Automation skips it.
                            </p>
                          )}
                        </td>
                        <td style={{ padding: '1rem 1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          {item.createdAt ? new Date(item.createdAt).toISOString().split('T')[0] : '2026-07-20'}
                        </td>
                        <td style={{ padding: '1rem 1.5rem', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', alignItems: 'center' }}>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', fontSize: '0.75rem', fontWeight: '600' }} onClick={() => setPreviewMedia(item)}>PREVIEW</button>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', fontSize: '0.75rem', fontWeight: '600' }} onClick={() => handleEditMedia(item)}>EDIT</button>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', fontSize: '0.75rem', fontWeight: '600' }} onClick={() => handleToggleActive(item)}>
                              {inactive ? 'ACTIVATE' : 'DEACTIVATE'}
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem', color: 'var(--error)' }} onClick={() => handleDeleteMedia(item.id)}>
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* EDIT MODAL */}
        {editingMedia && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '500px', width: '100%', padding: '2rem', position: 'relative', borderRadius: '16px' }}>
              <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '1.25rem' }}>Edit asset</h3>
              <p style={{ margin: '0 0 1.5rem 0', fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                {editingMedia.filename}
              </p>

              <div className="input-group" style={{ marginBottom: '1.5rem' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.35rem', display: 'block' }}>Base Caption — what this shows</label>
                <p style={{ margin: '0 0 0.6rem 0', fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  This is the only description the AI has of this file. Describe what
                  is actually on screen and why it matters — the caption writer builds
                  every post from it, alongside your business profile.
                </p>
                <textarea
                  rows="7"
                  value={editCaption}
                  onChange={(e) => setEditCaption(e.target.value)}
                  placeholder="e.g. Developer runs a post-quantum scan from a terminal; the result returns compliant in under a second."
                  style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', color: '#fff', resize: 'vertical', fontSize: '0.85rem', lineHeight: 1.5 }}
                />
              </div>

              <div className="input-group" style={{ marginBottom: '2rem' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'block' }}>Update Media (Optional)</label>
                <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem' }}>
                  <input type="file" onChange={(e) => setEditFile(e.target.files[0])} style={{ fontSize: '0.85rem', width: '100%', color: 'var(--text-muted)' }} />
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.5rem 0 0 0' }}>Leave empty to keep existing media.</p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button className="btn btn-secondary" onClick={() => setEditingMedia(null)} disabled={saving}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSaveEdit} disabled={saving}>
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* PREVIEW MODAL */}
        {previewMedia && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div style={{ position: 'absolute', top: '2rem', right: '2rem' }}>
              <button 
                onClick={() => setPreviewMedia(null)} 
                style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid var(--border-color)', color: '#fff', cursor: 'pointer', borderRadius: '50%', padding: '0.5rem', display: 'flex' }}
              >
                <X size={24} />
              </button>
            </div>
            <div className="glass-panel" style={{ maxWidth: '400px', width: '100%', position: 'relative', borderRadius: '16px', overflow: 'hidden' }}>
              <div style={{ width: '100%', aspectRatio: '9/16', background: '#000', position: 'relative' }}>
                {previewMedia.mimeType?.startsWith('video/') || previewMedia.filename?.endsWith('.mp4') ? (
                  <video controls autoPlay src={previewMedia.url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                  <img src={previewMedia.url} alt={previewMedia.filename} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                )}
              </div>
              <div style={{ padding: '1.5rem', background: 'var(--bg-card)' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'block' }}>Caption Content</label>
                <p style={{ fontSize: '0.85rem', lineHeight: 1.5, margin: 0 }}>
                  {previewMedia.caption || previewMedia.filename || 'No caption provided.'}
                </p>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default MediaCatalog;


