import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { Upload, Trash2, Edit, Play, Eye, X } from 'lucide-react';

const MediaCatalog = ({ user, token, showToast, activeWorkspaceId }) => {
  const [mediaList, setMediaList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [baseCaption, setBaseCaption] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  
  // Modals
  const [previewMedia, setPreviewMedia] = useState(null);
  const [editingMedia, setEditingMedia] = useState(null);
  const [editCaption, setEditCaption] = useState('');

  useEffect(() => {
    fetchMedia();
  }, [activeWorkspaceId]);

  const fetchMedia = async () => {
    try {
      const res = await authFetch(`${API_BASE}/marketing/media`, {}, token);
      if (res.ok) {
        setMediaList(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch media', err);
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
    setEditCaption(item.caption || item.filename || '');
  };

  const handleSaveEdit = async () => {
    // In a real app, send update to backend
    showToast('Campaign updated!');
    setEditingMedia(null);
    fetchMedia(); // Mock refresh
  };

  const handleDeactivate = (id) => {
    showToast('Campaign deactivated (Mock action)');
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
              Base Caption
            </label>
            <input 
              type="text" 
              className="input" 
              placeholder="Enter base caption for AI to rewrite..." 
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
                {mediaList.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No campaigns found. Upload media to create one.
                    </td>
                  </tr>
                ) : (
                  mediaList.map(item => {
                    const isVideo = item.mimeType?.startsWith('video/') || item.filename?.endsWith('.mp4');
                    const captionPreview = item.caption || item.filename || 'No caption available...';
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
                        <td style={{ padding: '1rem 1.5rem', maxWidth: '300px' }}>
                          <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                            {captionPreview}
                          </p>
                        </td>
                        <td style={{ padding: '1rem 1.5rem' }}>
                          <span style={{ 
                            fontSize: '0.75rem', fontWeight: '700', padding: '0.2rem 0.6rem', 
                            borderRadius: '4px', background: 'rgba(16,185,129,0.15)', color: 'var(--success)' 
                          }}>
                            ACTIVE
                          </span>
                        </td>
                        <td style={{ padding: '1rem 1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                          {item.createdAt ? new Date(item.createdAt).toISOString().split('T')[0] : '2026-07-20'}
                        </td>
                        <td style={{ padding: '1rem 1.5rem', textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', alignItems: 'center' }}>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', fontSize: '0.75rem', fontWeight: '600' }} onClick={() => setPreviewMedia(item)}>PREVIEW</button>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', fontSize: '0.75rem', fontWeight: '600' }} onClick={() => handleEditMedia(item)}>EDIT</button>
                            <button className="btn btn-secondary" style={{ padding: '0.4rem 0.7rem', fontSize: '0.75rem', fontWeight: '600' }} onClick={() => handleDeactivate(item.id)}>DEACTIVATE</button>
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
              <h3 style={{ margin: '0 0 1.5rem 0', fontSize: '1.25rem' }}>Edit Campaign</h3>
              
              <div className="input-group" style={{ marginBottom: '1.5rem' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'block' }}>Base Caption</label>
                <textarea 
                  rows="4" 
                  value={editCaption} 
                  onChange={(e) => setEditCaption(e.target.value)} 
                  style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', color: '#fff', resize: 'none' }}
                />
              </div>

              <div className="input-group" style={{ marginBottom: '2rem' }}>
                <label style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'block' }}>Update Media (Optional)</label>
                <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.4rem' }}>
                  <input type="file" style={{ fontSize: '0.85rem', width: '100%', color: 'var(--text-muted)' }} />
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.5rem 0 0 0' }}>Leave empty to keep existing media.</p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button className="btn btn-secondary" onClick={() => setEditingMedia(null)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSaveEdit}>Save</button>
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


