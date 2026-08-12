import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../config';
import { Upload, Trash2, Edit, Play, Eye, X, Sparkles, Copy, AlertTriangle, RefreshCw, Music, ShieldAlert, Folder, FolderPlus, FolderOpen, Layers } from 'lucide-react';

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
  const [showOnlyUnfinished, setShowOnlyUnfinished] = useState(false);
  const [fixing, setFixing] = useState(false);
  const [purgeOpen, setPurgeOpen] = useState(false);
  const [purgePreview, setPurgePreview] = useState(null);
  const [purgeTyped, setPurgeTyped] = useState('');
  const [purging, setPurging] = useState(false);
  
  // Modals
  const [previewMedia, setPreviewMedia] = useState(null);
  const [editingMedia, setEditingMedia] = useState(null);
  const [editCaption, setEditCaption] = useState('');
  const [editFile, setEditFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Folders. A folder publishes as ONE carousel post; loose files each post on
  // their own. Selection lives here rather than on the rows so the action bar
  // can act on a set spanning the whole table.
  const [folders, setFolders] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [openFolder, setOpenFolder] = useState(null);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [folderBusy, setFolderBusy] = useState(false);

  useEffect(() => {
    fetchMedia();
    fetchFolders();
    // A folder belongs to one business; carrying a selection across a
    // workspace switch would move another business's files.
    setSelectedIds([]);
    setOpenFolder(null);
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

  const fetchFolders = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/folders`, {}, token);
      if (res.ok) setFolders(await res.json());
    } catch (err) {
      console.error('Failed to fetch folders', err);
    }
  };

  const handleCreateFolder = async () => {
    const name = newFolderName.trim();
    if (!name) return;
    setFolderBusy(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      }, token);
      if (res.ok) {
        setNewFolderName('');
        setCreatingFolder(false);
        await fetchFolders();
        showToast(`Folder "${name}" created — tick files below and move them in.`, 'success');
      } else {
        showToast('Could not create the folder.', 'error');
      }
    } catch (err) {
      showToast('Could not reach the server.', 'error');
    } finally {
      setFolderBusy(false);
    }
  };

  const handleMoveToFolder = async (folderId) => {
    if (!selectedIds.length) return;
    setFolderBusy(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/folders/${folderId}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mediaIds: selectedIds }),
      }, token);
      if (res.ok) {
        const data = await res.json();
        setSelectedIds([]);
        await Promise.all([fetchMedia(), fetchFolders()]);
        // The warning is the server's, and it is the honest one: a folder of
        // 14 cannot post 14 slides however the UI phrases it.
        showToast(
          data.warning || `${data.moved} file(s) moved. This folder posts as one carousel of ${data.count}.`,
          data.warning ? 'warning' : 'success'
        );
      } else {
        showToast('Could not move those files.', 'error');
      }
    } catch (err) {
      showToast('Could not reach the server.', 'error');
    } finally {
      setFolderBusy(false);
    }
  };

  const handleUnfile = async (ids) => {
    if (!ids.length) return;
    setFolderBusy(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/folders/unfile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mediaIds: ids }),
      }, token);
      if (res.ok) {
        setSelectedIds([]);
        await Promise.all([fetchMedia(), fetchFolders()]);
        showToast('Taken out of the folder — each posts on its own again.', 'success');
      }
    } catch (err) {
      showToast('Could not reach the server.', 'error');
    } finally {
      setFolderBusy(false);
    }
  };

  const handleDeleteFolder = async (folder) => {
    if (!window.confirm(
      `Remove the folder "${folder.name}"?\n\nThe ${folder.count} file(s) inside are NOT deleted — ` +
      `they go back to posting one at a time.`
    )) return;
    setFolderBusy(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/folders/${folder.id}`, {
        method: 'DELETE',
      }, token);
      if (res.ok) {
        const data = await res.json();
        if (openFolder?.id === folder.id) setOpenFolder(null);
        await Promise.all([fetchMedia(), fetchFolders()]);
        showToast(`Folder removed. ${data.released} file(s) kept.`, 'success');
      }
    } catch (err) {
      showToast('Could not reach the server.', 'error');
    } finally {
      setFolderBusy(false);
    }
  };

  const toggleSelected = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  // Move one slide to an explicit position. The user picks "3" and it becomes
  // the third slide; everything else closes the gap around it. Sending the
  // whole desired order rather than a single index keeps the server's view
  // authoritative — there is no way for two slides to claim position 3.
  const handleSetPosition = async (folder, mediaId, newIndex) => {
    const items = (folders.find(f => f.id === folder.id)?.items || []);
    const current = items.findIndex(m => m.id === mediaId);
    if (current === -1 || newIndex === current) return;

    const reordered = items.map(m => m.id);
    reordered.splice(current, 1);
    reordered.splice(newIndex, 0, mediaId);

    setFolderBusy(true);
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/folders/${folder.id}/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mediaIds: reordered }),
      }, token);
      if (res.ok) {
        await fetchFolders();
      } else {
        showToast('Could not change the slide order.', 'error');
      }
    } catch (err) {
      showToast('Could not reach the server.', 'error');
    } finally {
      setFolderBusy(false);
    }
  };

  // A file that has been moved into a folder leaves this list and lives in the
  // folder instead — that is what "moving" it means, and leaving it in both
  // places made it look like the file would post twice. `showFiled` brings
  // them back into view when someone wants to see everything at once.
  const [showFiled, setShowFiled] = useState(false);
  const filedCount = mediaList.filter(m => m.folderId).length;
  const visibleMedia = showFiled ? mediaList : mediaList.filter(m => !m.folderId);

  // Sent in batches rather than one 242-file request: a single upload of a
  // whole library exceeds request size limits and gives no progress, and one
  // network blip loses the lot. Each batch is independent.
  //
  // Three, not eight. Each video is uploaded to storage and has its end card
  // composited, and the server is killed at a 120s request timeout — eight
  // videos could not finish, so every batch returned 500.
  const BULK_BATCH = 3;

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // A bulk import does captioning and branding in the background, and
  // background work does not survive a restart. Rather than making the user
  // re-upload a library to repair it, this finishes whatever was left.
  const unfinished = mediaList.filter(
    m => (m.mimeType || '').startsWith('video/') && (m.needsCaption || m.branded === false)
  );

  // Tracks are catalog rows like anything else, but they are never posted —
  // they are the pool a silent clip draws a music bed from during branding.
  const musicTracks = mediaList.filter(
    m => (m.mimeType || '').startsWith('audio/')
  );


  // Deleting a whole catalog is not undoable, so it happens in two steps: the
  // server reports exactly what would go, and only removes anything once the
  // workspace name is typed back. Same call, with and without the name.
  const openPurge = async () => {
    setPurgeTyped('');
    setPurgeOpen(true);
    setPurgePreview(null);
    try {
      const res = await authFetch(
        `${API_BASE}/marketing/media/purge`, { method: 'POST' }, token);
      setPurgePreview(await res.json());
    } catch (err) {
      showToast('Could not read the catalog', 'error');
      setPurgeOpen(false);
    }
  };

  const confirmPurge = async () => {
    setPurging(true);
    try {
      const res = await authFetch(
        `${API_BASE}/marketing/media/purge?confirm_name=${encodeURIComponent(purgeTyped)}`,
        { method: 'POST' }, token);
      const d = await res.json();
      if (d.confirmed) {
        showToast(d.message, 'success');
        setPurgeOpen(false);
        fetchMedia();
      } else {
        showToast('That name did not match', 'error');
      }
    } catch (err) {
      showToast('Delete failed', 'error');
    } finally {
      setPurging(false);
    }
  };

  const handleFixUnfinished = async () => {
    setFixing(true);
    try {
      const res = await authFetch(
        `${API_BASE}/marketing/media/backfill`,
        { method: 'POST' },
        token
      );
      const d = await res.json();
      showToast(d.message || 'Repair started', res.ok ? 'success' : 'error');
      // The work runs in the background, so give it a moment before the list
      // is refetched or nothing will look different and the user will click
      // again.
      setTimeout(fetchMedia, 4000);
    } catch (err) {
      showToast('Could not start the repair. Try again in a moment.', 'error');
    } finally {
      setFixing(false);
    }
  };

  const handleBulkUpload = async () => {
    if (!bulkFiles.length) return;
    setBulkUploading(true);
    setBulkResult(null);

    // Audio is accepted too, but it is not content — tracks are the pool a
    // silent clip draws a music bed from, because Instagram's own music picker
    // only exists inside the app and cannot be reached from the publishing API.
    const media = bulkFiles.filter(f =>
      f.type.startsWith('image/') || f.type.startsWith('video/') ||
      f.type.startsWith('audio/'));
    if (!media.length) {
      setBulkResult({ message: 'That folder had no images, videos or audio in it.', failed: 0 });
      setBulkUploading(false);
      return;
    }

    // Pinned once, for every batch of this upload.
    //
    // authFetch otherwise reads the active workspace from localStorage at the
    // moment each request fires, and a bulk upload is dozens of sequential
    // requests over several minutes. localStorage is shared across tabs of the
    // same origin, so switching business in ANOTHER TAB silently redirected
    // every remaining batch into that business. One folder ended up split
    // across five workspaces that way, and nothing in the UI showed it
    // happening.
    const uploadWorkspaceId =
      activeWorkspaceId || localStorage.getItem('activeWorkspaceId');
    if (!uploadWorkspaceId) {
      setBulkResult({ message: 'Select a business before uploading.', failed: 0 });
      setBulkUploading(false);
      return;
    }
    const pinnedWorkspace = { 'X-Workspace-Id': uploadWorkspaceId };

    let stored = 0, failed = 0, described = 0, skipped = 0, lastError = null;
    try {
      // Batched by SIZE, not by count. Three clips sounds small until three
      // of the large ones land together: this folder's biggest three are 33MB
      // in a single POST, which the host reset mid-body every time
      // (ERR_HTTP2_PROTOCOL_ERROR, identically on all four retries — a limit,
      // not load). Capping the payload keeps every request comfortably under
      // it regardless of which files happen to be adjacent.
      const MAX_BATCH_BYTES = 6 * 1024 * 1024;

      let i = 0;
      while (i < media.length) {
        const batch = [];
        let bytes = 0;
        while (i < media.length && batch.length < BULK_BATCH) {
          const size = media[i].size || 0;
          // Always take at least one, or a file above the cap never uploads.
          if (batch.length && bytes + size > MAX_BATCH_BYTES) break;
          batch.push(media[i]);
          bytes += size;
          i += 1;
        }
        const done = i;
        setBulkProgress(
          `${done} / ${media.length}` + (skipped ? ` · ${skipped} already here` : '')
        );

        const form = new FormData();
        batch.forEach(f => form.append('files', f));
        form.append('write_captions', autoCaption ? 'true' : 'false');

        // Retried with backoff. Uploading a whole library is dozens of
        // multi-megabyte POSTs in a few minutes, and the host's edge starts
        // rejecting them — a 403 with no CORS header, which the browser
        // reports as a CORS failure because the response never reached the
        // application at all. Backing off clears it; hammering does not.
        let ok = false;
        for (let attempt = 0; attempt < 4 && !ok; attempt++) {
          if (attempt) {
            setBulkProgress(`${done} / ${media.length} — retrying`);
            await sleep(2000 * Math.pow(2, attempt - 1));   // 2s, 4s, 8s
          }
          try {
            const res = await authFetch(
              `${API_BASE}/marketing/media/bulk-upload`,
              { method: 'POST', body: form, headers: pinnedWorkspace },
              token
            );
            // Surface WHAT failed, not just that something did. A bare
            // "HTTP 500" in the console cost several rounds of guessing.
            const body = await res.text();
            if (!res.ok) {
              lastError = `HTTP ${res.status}: ${body.slice(0, 200)}`;
              throw new Error(lastError);
            }
            const d = JSON.parse(body);
            stored += d.stored || 0;
            failed += d.failed || 0;
            described += d.described || 0;
            if (d.message && d.success === false) lastError = d.message;
            ok = true;
          } catch (err) {
            console.warn(`batch attempt ${attempt + 1} failed`, err);
            if (!lastError) lastError = String(err.message || err).slice(0, 200);
          }
        }
        if (!ok) {
          // One exhausted batch must not abandon the rest of the folder.
          failed += batch.length;
        }

        // A short gap between batches keeps the upload under whatever rate the
        // edge is enforcing. It costs a couple of minutes across a library and
        // is far cheaper than a failed run.
        await sleep(700);
      }

      // If the business was switched while this ran, the files still went where
      // the upload started -- but the catalog on screen is now a different one,
      // so say so rather than letting it look like nothing arrived.
      const switchedAway =
        (localStorage.getItem('activeWorkspaceId') || '') !== uploadWorkspaceId;

      setBulkResult({
        message:
          `${stored} added` +
          (skipped ? `, ${skipped} already in the catalog` : '') +
          (failed ? `, ${failed} failed` : '') +
          ` — ${media.length} selected` +
          (switchedAway
            ? '. You changed business while this was running; the files went to '
              + 'the one you started from, not the one shown now.'
            : ''),
        failed,
        error: stored === 0 && !skipped ? lastError : null,
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
              {bulkResult.error && (
                <span style={{ display: 'block', marginTop: '0.4rem', opacity: 0.85 }}>
                  {bulkResult.error}
                </span>
              )}
            </p>
          )}
        </div>

        {/* Music for clips that arrived without any.
            Instagram's own catalogue is reachable only inside the app — the
            publishing API has no field for a track — so a silent clip posted
            automatically stays silent. Tracks uploaded here are mixed in
            during branding, and only under clips that have no audio. */}
        <div className="glass-panel" style={{ marginBottom: '1.5rem', padding: '1.25rem 1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Music for silent clips
          </label>
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            {musicTracks.length > 0
              ? <><strong>{musicTracks.length}</strong> track{musicTracks.length === 1 ? '' : 's'} loaded. Clips with no audio get one mixed in automatically, rotated across the library. Clips that already have sound are never touched.</>
              : <>No tracks yet. Clips with no audio will post silent. Download what you want from{' '}
                <a href="https://www.facebook.com/sound" target="_blank" rel="noopener noreferrer"
                   style={{ color: 'var(--accent, #6ea8fe)' }}>Meta Sound Collection</a>
                {' '}— it is free and licensed specifically for Instagram and Facebook — then add the files here.</>}
          </p>
          <input
            type="file"
            id="music-upload"
            multiple
            accept="audio/*"
            onChange={(e) => setBulkFiles(Array.from(e.target.files || []))}
            style={{ display: 'none' }}
          />
          <button className="btn btn-secondary" style={{ height: 38 }}
            onClick={() => document.getElementById('music-upload').click()}
            disabled={bulkUploading}>
            <Music size={15} /> Add music tracks
          </button>
          <span style={{ marginLeft: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            then press Upload above
          </span>
        </div>

        {/* Two things a bulk import can silently leave undone. Surfacing the
            count means the user finds out here rather than in a published
            post. */}
        {unfinished.length > 0 && (
          <div className="glass-panel" style={{
            marginBottom: '1rem', padding: '0.9rem 1.25rem', display: 'flex',
            flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem',
            border: '1px solid rgba(224,168,0,0.35)',
          }}>
            <AlertTriangle size={17} color="#e0a800" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: '0.88rem' }}>
              <strong>{unfinished.length}</strong> video{unfinished.length === 1 ? '' : 's'} not finished
              {' — '}
              {unfinished.filter(m => m.needsCaption).length} without a description,
              {' '}
              {unfinished.filter(m => m.branded === false).length} without the watermark.
            </span>
            <button className="btn btn-secondary" style={{ height: 36 }}
              onClick={() => setShowOnlyUnfinished(v => !v)}>
              {showOnlyUnfinished ? 'Show all' : 'Show only these'}
            </button>
            <button className="btn btn-primary" style={{ height: 36, marginLeft: 'auto' }}
              onClick={handleFixUnfinished} disabled={fixing}>
              {fixing ? <span className="spinner"></span> : <><RefreshCw size={15} /> Describe & brand them</>}
            </button>
          </div>
        )}

        {/* FOLDERS — each folder publishes as ONE carousel post */}
        <div className="glass-panel" style={{ padding: '1.1rem 1.35rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
            <Layers size={17} color="var(--primary-color)" />
            <strong style={{ fontSize: '0.95rem' }}>Carousel folders</strong>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Every file in a folder goes out as one carousel post. Loose files post one at a time.
            </span>
            {filedCount > 0 && (
              <button className="btn btn-secondary" style={{ height: 34, marginLeft: 'auto', fontSize: '0.8rem' }}
                onClick={() => setShowFiled(v => !v)}>
                {showFiled
                  ? `Hide the ${filedCount} filed file${filedCount === 1 ? '' : 's'}`
                  : `Show the ${filedCount} filed file${filedCount === 1 ? '' : 's'} in the table`}
              </button>
            )}
            <button className="btn btn-secondary"
              style={{ height: 34, marginLeft: filedCount > 0 ? 0 : 'auto' }}
              onClick={() => setCreatingFolder(v => !v)}>
              <FolderPlus size={15} /> New folder
            </button>
          </div>

          {creatingFolder && (
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.85rem', flexWrap: 'wrap' }}>
              <input
                autoFocus
                value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleCreateFolder(); }}
                placeholder="Folder name — e.g. Diwali launch set"
                style={{
                  flex: '1 1 260px', padding: '0.55rem 0.8rem', borderRadius: 8,
                  border: '1px solid var(--border-color)', background: 'rgba(255,255,255,0.04)',
                  color: 'inherit', fontSize: '0.88rem',
                }}
              />
              <button className="btn btn-primary" style={{ height: 38 }}
                onClick={handleCreateFolder} disabled={folderBusy || !newFolderName.trim()}>
                Create
              </button>
              <button className="btn btn-secondary" style={{ height: 38 }}
                onClick={() => { setCreatingFolder(false); setNewFolderName(''); }}>
                Cancel
              </button>
            </div>
          )}

          {folders.length > 0 && (
            <div style={{ display: 'flex', gap: '0.7rem', flexWrap: 'wrap', marginTop: '0.95rem' }}>
              {folders.map(f => (
                <div key={f.id} style={{
                  border: '1px solid var(--border-color)', borderRadius: 10,
                  padding: '0.65rem 0.8rem', minWidth: 190, background: 'rgba(255,255,255,0.03)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {f.count ? <FolderOpen size={16} color="#6ea8fe" /> : <Folder size={16} color="var(--text-muted)" />}
                    <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>{f.name}</span>
                  </div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                    {f.count} file{f.count === 1 ? '' : 's'} · one carousel post
                  </div>
                  {f.warning && (
                    <div style={{ fontSize: '0.72rem', color: '#fbbf24', marginTop: '0.35rem', lineHeight: 1.35 }}>
                      {f.warning}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.55rem', flexWrap: 'wrap' }}>
                    {selectedIds.length > 0 && (
                      <button className="btn btn-primary" style={{ height: 30, fontSize: '0.76rem', padding: '0 0.6rem' }}
                        onClick={() => handleMoveToFolder(f.id)} disabled={folderBusy}>
                        Move {selectedIds.length} here
                      </button>
                    )}
                    <button className="btn btn-secondary" style={{ height: 30, fontSize: '0.76rem', padding: '0 0.6rem' }}
                      onClick={() => setOpenFolder(openFolder?.id === f.id ? null : f)}>
                      {openFolder?.id === f.id ? 'Hide' : 'View'}
                    </button>
                    <button className="btn btn-secondary" style={{ height: 30, fontSize: '0.76rem', padding: '0 0.6rem', color: '#f87171' }}
                      onClick={() => handleDeleteFolder(f)} disabled={folderBusy}>
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {openFolder && (
            <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.85rem' }}>
              <div style={{ fontSize: '0.83rem', marginBottom: '0.6rem' }}>
                <strong>{openFolder.name}</strong>
                <span style={{ color: 'var(--text-muted)' }}> — slides in posting order</span>
              </div>
              {(folders.find(f => f.id === openFolder.id)?.items || []).length === 0 ? (
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
                  Empty. Tick files in the table below, then press “Move here”.
                </p>
              ) : (
                <div style={{ display: 'flex', gap: '0.7rem', flexWrap: 'wrap' }}>
                  {(() => {
                    const items = folders.find(f => f.id === openFolder.id)?.items || [];
                    return items.map((m, i) => {
                      // Instagram publishes the first ten. Showing which slides
                      // fall outside that is the whole point of letting the
                      // order be edited.
                      const willPost = i < 10;
                      return (
                        <div key={m.id} style={{ width: 86 }}>
                          <div style={{
                            width: 86, height: 86, borderRadius: 8, overflow: 'hidden',
                            background: '#000', position: 'relative',
                            opacity: willPost ? 1 : 0.35,
                            outline: willPost ? 'none' : '1px dashed #fbbf24',
                          }}>
                            {(m.mimeType || '').startsWith('video/')
                              ? <video src={m.url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                              : <img src={m.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />}
                            <button
                              onClick={() => handleUnfile([m.id])}
                              title="Take out of this folder"
                              style={{
                                position: 'absolute', top: 3, right: 3, background: 'rgba(0,0,0,0.75)',
                                border: 'none', borderRadius: 4, color: '#f87171', cursor: 'pointer',
                                padding: '0 5px', lineHeight: 1.35, fontSize: '0.82rem',
                              }}>×</button>
                          </div>
                          {/* Explicit placement — pick the slide number this
                              image should occupy. */}
                          <select
                            value={i}
                            disabled={folderBusy}
                            onChange={e => handleSetPosition(openFolder, m.id, Number(e.target.value))}
                            title="Slide position in the carousel"
                            style={{
                              width: '100%', marginTop: 4, fontSize: '0.72rem',
                              padding: '2px 4px', borderRadius: 5, cursor: 'pointer',
                              background: 'rgba(255,255,255,0.06)', color: 'inherit',
                              border: '1px solid var(--border-color)',
                            }}
                          >
                            {items.map((_, n) => (
                              <option key={n} value={n}>
                                {n + 1}{n >= 10 ? ' — not posted' : ''}
                              </option>
                            ))}
                          </select>
                        </div>
                      );
                    });
                  })()}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Selection bar — appears only when files are ticked */}
        {selectedIds.length > 0 && (
          <div className="glass-panel" style={{
            padding: '0.75rem 1.25rem', marginBottom: '1rem', display: 'flex',
            alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap',
            border: '1px solid rgba(110,168,254,0.35)',
          }}>
            <strong style={{ fontSize: '0.88rem' }}>{selectedIds.length} selected</strong>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {folders.length === 0
                ? 'Create a folder above to group them into one carousel.'
                : 'Press “Move here” on a folder above.'}
            </span>
            <button className="btn btn-secondary" style={{ height: 32, fontSize: '0.8rem' }}
              onClick={() => handleUnfile(selectedIds)} disabled={folderBusy}>
              Take out of folders
            </button>
            <button className="btn btn-secondary" style={{ height: 32, fontSize: '0.8rem', marginLeft: 'auto' }}
              onClick={() => setSelectedIds([])}>
              Clear
            </button>
          </div>
        )}

        {/* TABLE SECTION */}
        <div className="glass-panel" style={{ overflowX: 'auto', border: 'none', background: 'transparent', boxShadow: 'none' }}>
          <div className="glass-panel" style={{ overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.8rem', textTransform: 'uppercase' }}>
                  <th style={{ padding: '1rem 0 1rem 1.25rem', fontWeight: '600', width: 34 }}></th>
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
                    <td colSpan="6" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      <span className="spinner" style={{ width: 20, height: 20 }} />
                    </td>
                  </tr>
                ) : loadError ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '2.5rem', textAlign: 'center' }}>
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
                ) : visibleMedia.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      {mediaList.length === 0
                        ? 'No media yet. Upload a file above, or generate one in AI Video Studio.'
                        : `Every file is inside a folder. Use “Show the ${filedCount} filed files in the table” above to see them.`}
                    </td>
                  </tr>
                ) : (
                  (showOnlyUnfinished ? unfinished : visibleMedia).map(item => {
                    const isVideo = item.mimeType?.startsWith('video/') || item.filename?.endsWith('.mp4');
                    const isAudio = item.mimeType?.startsWith('audio/');
                    const caption = item.caption || item.prompt || '';
                    const inactive = item.isActive === false;
                    const inFolder = folders.find(f => f.id === item.folderId);
                    return (
                      <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '1rem 0 1rem 1.25rem', width: 34 }}>
                          {/* Tracks are never posted, so grouping one into a
                              carousel would only produce a broken slide. */}
                          {!isAudio && (
                            <input
                              type="checkbox"
                              checked={selectedIds.includes(item.id)}
                              onChange={() => toggleSelected(item.id)}
                              style={{ width: 15, height: 15, cursor: 'pointer' }}
                            />
                          )}
                        </td>
                        <td style={{ padding: '1rem 1.5rem', width: '80px' }}>
                          <div style={{ width: '56px', height: '56px', borderRadius: '8px', overflow: 'hidden', background: '#000', position: 'relative' }}>
                            {isAudio ? (
                              // A track has no frame to show, and an <img>
                              // pointed at an mp3 renders as a broken icon.
                              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(110,168,254,0.12)' }}>
                                <Music size={20} color="#6ea8fe" />
                              </div>
                            ) : isVideo ? (
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
                            {item.branded === false && (
                              <span style={{ marginLeft: '0.5rem', color: '#fbbf24' }}>
                                &middot; no watermark yet
                              </span>
                            )}
                            {inFolder && (
                              <span style={{ marginLeft: '0.5rem', color: '#6ea8fe' }}>
                                &middot; in “{inFolder.name}” — posts as part of that carousel
                              </span>
                            )}
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

        {/* Danger zone. Deliberately last, visually separate, and never a
            single click -- it deletes the catalog and the stored files. */}
        <div style={{
          marginTop: '2rem', padding: '1.25rem 1.5rem', borderRadius: 12,
          border: '1px solid rgba(255,90,90,0.35)', background: 'rgba(255,60,60,0.04)',
        }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.4rem', fontSize: '0.85rem', fontWeight: 600, color: '#ff8080', textTransform: 'uppercase' }}>
            <ShieldAlert size={15} /> Danger zone
          </label>
          <p style={{ margin: '0 0 0.9rem', fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Delete every image, video and music track in this business, and the
            stored files behind them. This cannot be undone.
          </p>
          <button className="btn" style={{ height: 38, background: 'rgba(255,60,60,0.15)', color: '#ff8080', border: '1px solid rgba(255,90,90,0.4)' }}
            onClick={openPurge} disabled={purging}>
            <Trash2 size={15} /> Delete all media
          </button>
        </div>

        {purgeOpen && (
          <div onClick={() => !purging && setPurgeOpen(false)} style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
          }}>
            <div onClick={e => e.stopPropagation()} className="glass-panel" style={{ maxWidth: 460, width: '100%', padding: '1.5rem' }}>
              <h3 style={{ margin: '0 0 0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ff8080' }}>
                <ShieldAlert size={18} /> Delete all media
              </h3>
              {!purgePreview ? (
                <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                  <span className="spinner" style={{ width: 14, height: 14 }} /> Checking what is here...
                </p>
              ) : (
                <>
                  <p style={{ fontSize: '0.88rem', lineHeight: 1.6, marginTop: 0 }}>
                    This permanently deletes <strong>{purgePreview.total}</strong> asset
                    {purgePreview.total === 1 ? '' : 's'} from <strong>{purgePreview.workspace}</strong>
                    {' '}&mdash; {purgePreview.videos} video{purgePreview.videos === 1 ? '' : 's'},
                    {' '}{purgePreview.images} image{purgePreview.images === 1 ? '' : 's'}
                    {purgePreview.audio > 0 && `, ${purgePreview.audio} music track${purgePreview.audio === 1 ? '' : 's'}`}
                    {' '}&mdash; and removes {purgePreview.storedFiles} stored file
                    {purgePreview.storedFiles === 1 ? '' : 's'}.
                  </p>
                  {purgePreview.elsewhere > 0 && (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                      {purgePreview.elsewhere} older file{purgePreview.elsewhere === 1 ? ' is' : 's are'} hosted
                      outside our storage and cannot be deleted from here; the catalog
                      entries go either way.
                    </p>
                  )}
                  <p style={{ fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                    Type <strong>{purgePreview.workspace}</strong> to confirm:
                  </p>
                  <input value={purgeTyped} onChange={e => setPurgeTyped(e.target.value)}
                    autoFocus placeholder={purgePreview.workspace}
                    style={{ width: '100%', padding: '0.6rem 0.75rem', borderRadius: 8, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', marginBottom: '1rem' }} />
                  <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'flex-end' }}>
                    <button className="btn btn-secondary" style={{ height: 38 }}
                      onClick={() => setPurgeOpen(false)} disabled={purging}>Cancel</button>
                    <button className="btn" style={{ height: 38, background: purgeTyped === purgePreview.workspace ? '#c62828' : 'rgba(255,255,255,0.08)', color: '#fff', cursor: purgeTyped === purgePreview.workspace ? 'pointer' : 'not-allowed' }}
                      onClick={confirmPurge}
                      disabled={purging || purgeTyped !== purgePreview.workspace}>
                      {purging ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Trash2 size={15} />} Delete everything
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default MediaCatalog;


