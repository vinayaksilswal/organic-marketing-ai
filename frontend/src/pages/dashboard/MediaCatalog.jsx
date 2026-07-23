import React, { useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../../App';
import { UploadCloud, Folder, Search, Link as LinkIcon, Plus, Trash2, Edit3, Film, Image as ImageIcon, ExternalLink, RefreshCw, X, ShoppingBag } from 'lucide-react';

const MediaCatalog = ({ user, token, showToast, activeWorkspaceId }) => {
  const [activeTab, setActiveTab] = useState('media'); // 'media' or 'products'
  
  // Media state
  const [mediaList, setMediaList] = useState([]);
  const [mediaFilter, setMediaFilter] = useState('all'); // all, image, video, ai
  const [searchQuery, setSearchQuery] = useState('');
  const [uploading, setUploading] = useState(false);
  const [previewMedia, setPreviewMedia] = useState(null);

  // E-Commerce product state
  const [products, setProducts] = useState([]);
  const [catalogUrl, setCatalogUrl] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [editingProductId, setEditingProductId] = useState(null);
  
  // Product Form state
  const [prodTitle, setProdTitle] = useState('');
  const [prodPrice, setProdPrice] = useState('');
  const [prodDescription, setProdDescription] = useState('');
  const [prodUrl, setProdUrl] = useState('');
  const [prodImageUrl, setProdImageUrl] = useState('');
  const [prodSubmitting, setProdSubmitting] = useState(false);

  useEffect(() => {
    if (activeTab === 'media') {
      fetchMedia();
    } else {
      fetchProducts();
    }
  }, [activeWorkspaceId, activeTab]);

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

  const fetchProducts = async () => {
    try {
      const res = await authFetch(`${API_BASE}/ecommerce/products`, {}, token);
      if (res.ok) {
        const body = await res.json();
        setProducts(body.data || []);
      }
    } catch (err) {
      console.error('Failed to fetch products', err);
    }
  };

  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append('file', files[i]);

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
      }
      showToast('Media uploaded successfully!');
      fetchMedia();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteMedia = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Delete this media item from catalog?')) return;
    try {
      const res = await authFetch(`${API_BASE}/marketing/media/${id}`, {
        method: 'DELETE'
      }, token);
      if (res.ok) {
        showToast('Media item deleted!');
        fetchMedia();
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const syncCatalog = async () => {
    if (!catalogUrl.trim()) return showToast('Please enter catalog feed URL', true);
    
    setSyncing(true);
    try {
      const res = await authFetch(`${API_BASE}/ecommerce/sync-catalog`, {
        method: 'POST',
        body: JSON.stringify({ url: catalogUrl })
      }, token);
      if (res.ok) {
        const data = await res.json();
        showToast(data.message || 'Catalog synchronized!');
        setCatalogUrl('');
        fetchProducts();
      } else {
        throw new Error('Sync failed');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setSyncing(false);
    }
  };

  const openProductModal = (product = null) => {
    if (product) {
      setEditingProductId(product.id);
      setProdTitle(product.title || '');
      setProdPrice(product.price || '');
      setProdDescription(product.description || '');
      setProdUrl(product.url || '');
      setProdImageUrl(product.imageUrl || '');
    } else {
      setEditingProductId(null);
      setProdTitle('');
      setProdPrice('');
      setProdDescription('');
      setProdUrl('');
      setProdImageUrl('');
    }
    setIsProductModalOpen(true);
  };

  const handleSaveProduct = async () => {
    if (!prodTitle.trim()) return showToast('Product title is required', true);
    
    setProdSubmitting(true);
    try {
      const payload = {
        title: prodTitle,
        price: parseFloat(prodPrice) || 0,
        description: prodDescription,
        url: prodUrl,
        imageUrl: prodImageUrl
      };

      const url = editingProductId 
        ? `${API_BASE}/ecommerce/products/${editingProductId}`
        : `${API_BASE}/ecommerce/products`;

      const res = await authFetch(url, {
        method: editingProductId ? 'PUT' : 'POST',
        body: JSON.stringify(payload)
      }, token);

      if (res.ok) {
        showToast(editingProductId ? 'Product updated!' : 'Product added!');
        setIsProductModalOpen(false);
        fetchProducts();
      } else {
        throw new Error('Failed to save product');
      }
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setProdSubmitting(false);
    }
  };

  const handleDeleteProduct = async (id) => {
    if (!window.confirm('Delete this product?')) return;
    try {
      const res = await authFetch(`${API_BASE}/ecommerce/products/${id}`, {
        method: 'DELETE'
      }, token);
      if (res.ok) {
        showToast('Product deleted!');
        fetchProducts();
      }
    } catch (err) {
      showToast(err.message, true);
    }
  };

  // Filter media items
  const filteredMedia = mediaList.filter(item => {
    const matchesSearch = item.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const isVideo = item.mimeType?.startsWith('video/') || item.filename.endsWith('.mp4');
    const isAI = item.filename.startsWith('AI_Render_');
    
    if (!matchesSearch) return false;
    if (mediaFilter === 'image') return !isVideo;
    if (mediaFilter === 'video') return isVideo;
    if (mediaFilter === 'ai') return isAI;
    return true;
  });

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0' }}>
        <div style={{ marginBottom: '2rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem' }}>Media Repository & Product Catalog</h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
            Unified asset library for manual uploads, AI Video renders, and e-commerce `catalog.txt` feeds.
          </p>
        </div>
        
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
          <button 
            className={`btn ${activeTab === 'media' ? 'btn-primary' : 'btn-secondary'}`} 
            onClick={() => setActiveTab('media')}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <ImageIcon size={18} /> Unified Media Library ({mediaList.length})
          </button>
          <button 
            className={`btn ${activeTab === 'products' ? 'btn-primary' : 'btn-secondary'}`} 
            onClick={() => setActiveTab('products')}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
          >
            <ShoppingBag size={18} /> E-Commerce Catalog ({products.length})
          </button>
        </div>

        {/* MEDIA TAB */}
        {activeTab === 'media' && (
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                {['all', 'image', 'video', 'ai'].map(f => (
                  <button 
                    key={f}
                    className={`btn ${mediaFilter === f ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', textTransform: 'capitalize' }}
                    onClick={() => setMediaFilter(f)}
                  >
                    {f === 'ai' ? '⚡ AI Rendered' : f}
                  </button>
                ))}
              </div>

              <div className="input-group" style={{ marginBottom: 0, width: '280px' }}>
                <div style={{ position: 'relative' }}>
                  <Search size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: 'var(--text-muted)' }} />
                  <input 
                    type="text" 
                    placeholder="Search media..." 
                    style={{ paddingLeft: '2.5rem' }}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* Upload Dropzone */}
            <div className="dropzone" style={{ marginBottom: '2rem', position: 'relative', cursor: 'pointer' }}>
              <input 
                type="file" 
                multiple 
                accept="image/*,video/*"
                onChange={handleFileUpload} 
                style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer' }}
              />
              <UploadCloud className="dropzone-icon" />
              <h4 style={{ margin: '0.5rem 0 0.25rem 0' }}>
                {uploading ? 'Uploading assets...' : 'Upload Media Assets'}
              </h4>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                Drag & Drop or click to browse images and videos (MP4, MOV, PNG, JPG)
              </p>
            </div>

            {/* Media Grid */}
            <div className="media-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1.25rem' }}>
              {filteredMedia.length === 0 ? (
                <div style={{ gridColumn: '1 / -1', padding: '3rem 0', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No media assets found in this workspace. Upload files or render a video in AI Video Studio.
                </div>
              ) : (
                filteredMedia.map(item => {
                  const isVideo = item.mimeType?.startsWith('video/') || item.filename.endsWith('.mp4');
                  const isAI = item.filename.startsWith('AI_Render_');
                  return (
                    <div 
                      key={item.id} 
                      className="glass-panel"
                      style={{ 
                        overflow: 'hidden', 
                        borderRadius: '12px', 
                        display: 'flex', 
                        flexDirection: 'column',
                        border: '1px solid var(--border-color)',
                        cursor: 'pointer'
                      }}
                      onClick={() => setPreviewMedia(item)}
                    >
                      <div style={{ aspectRatio: '16/9', background: '#000', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {isVideo ? (
                          <video src={item.url} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : (
                          <img src={item.url} alt={item.filename} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        )}
                        {isVideo && (
                          <div style={{ position: 'absolute', top: '0.5rem', right: '0.5rem', background: 'rgba(0,0,0,0.7)', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                            <Film size={12} color="var(--primary-color)" /> VIDEO
                          </div>
                        )}
                        {isAI && (
                          <div style={{ position: 'absolute', top: '0.5rem', left: '0.5rem', background: 'var(--primary-color)', color: '#fff', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.65rem', fontWeight: '700' }}>
                            ⚡ AI GENERATED
                          </div>
                        )}
                      </div>
                      <div style={{ padding: '0.75rem', fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ overflow: 'hidden' }}>
                          <p style={{ margin: 0, fontWeight: '600', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.filename}</p>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {item.createdAt ? new Date(item.createdAt).toLocaleDateString() : 'Recent'}
                          </span>
                        </div>
                        <button 
                          className="btn btn-secondary" 
                          style={{ padding: '0.35rem', color: 'var(--error)', flexShrink: 0, marginLeft: '0.5rem' }} 
                          onClick={(e) => handleDeleteMedia(e, item.id)} 
                          title="Delete media asset"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* PRODUCTS TAB */}
        {activeTab === 'products' && (
          <div className="glass-panel" style={{ padding: '2rem' }}>
            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ margin: '0 0 0.5rem 0' }}>E-Commerce Catalog Ingestion</h3>
              <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
                Automatically ingest products by entering your website URL or a link to a <code>catalog.txt</code>, XML, or CSV feed.
              </p>
            </div>

            {/* Sync URL Box */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', flexWrap: 'wrap' }}>
              <div className="input-group" style={{ flex: 1, marginBottom: 0, minWidth: '280px' }}>
                <div style={{ position: 'relative' }}>
                  <LinkIcon size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
                  <input 
                    type="url" 
                    placeholder="https://yourstore.com/catalog.txt or https://store.com/feed.xml" 
                    style={{ paddingLeft: '2.5rem' }}
                    value={catalogUrl}
                    onChange={(e) => setCatalogUrl(e.target.value)}
                  />
                </div>
              </div>
              <button className="btn btn-primary" onClick={syncCatalog} disabled={syncing || !catalogUrl} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {syncing ? <span className="spinner"></span> : <><RefreshCw size={16} /> Sync Catalog Feed</>}
              </button>
            </div>

            <hr style={{ borderColor: 'var(--border-color)', margin: '2rem 0' }} />
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h4 style={{ margin: 0, fontSize: '1.1rem' }}>Managed Products Catalog ({products.length})</h4>
              <button className="btn btn-secondary" style={{ fontSize: '0.85rem' }} onClick={() => openProductModal(null)}>
                + Add Product Manually
              </button>
            </div>
            
            <div className="media-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
              {products.length === 0 ? (
                <div style={{ gridColumn: '1 / -1', padding: '3rem 0', textAlign: 'center', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                  <p style={{ color: 'var(--text-muted)', margin: 0 }}>No products found. Sync your catalog or add a product manually.</p>
                </div>
              ) : (
                products.map(prod => (
                  <div key={prod.id} className="glass-panel" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', borderRadius: '12px' }}>
                    {prod.imageUrl && (
                      <img src={prod.imageUrl} alt={prod.title} style={{ width: '100%', height: '160px', objectFit: 'cover', borderRadius: '8px' }} />
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <h4 style={{ margin: 0, fontSize: '1rem' }}>{prod.title}</h4>
                      {prod.price && (
                        <span style={{ fontWeight: '700', color: 'var(--success)', fontSize: '0.95rem' }}>
                          ${prod.price.toFixed(2)}
                        </span>
                      )}
                    </div>
                    {prod.description && (
                      <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)', flex: 1, lineHeight: 1.4 }}>
                        {prod.description}
                      </p>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-color)' }}>
                      {prod.url ? (
                        <a href={prod.url} target="_blank" rel="noreferrer" style={{ fontSize: '0.75rem', color: 'var(--secondary-color)', display: 'flex', alignItems: 'center', gap: '0.3rem', textDecoration: 'none' }}>
                          View Product <ExternalLink size={12} />
                        </a>
                      ) : <span />}
                      <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button className="btn btn-secondary" style={{ padding: '0.35rem' }} onClick={() => openProductModal(prod)} title="Edit">
                          <Edit3 size={14} />
                        </button>
                        <button className="btn btn-secondary" style={{ padding: '0.35rem', color: 'var(--error)' }} onClick={() => handleDeleteProduct(prod.id)} title="Delete">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Lightbox Preview Modal */}
        {previewMedia && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '720px', width: '100%', padding: '1.5rem', position: 'relative' }}>
              <button onClick={() => setPreviewMedia(null)} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
                <X size={24} />
              </button>
              <h3 style={{ margin: '0 0 1rem 0' }}>{previewMedia.filename}</h3>
              {previewMedia.mimeType?.startsWith('video/') || previewMedia.filename.endsWith('.mp4') ? (
                <video controls autoPlay src={previewMedia.url} style={{ width: '100%', maxHeight: '420px', borderRadius: '12px' }} />
              ) : (
                <img src={previewMedia.url} alt={previewMedia.filename} style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '12px' }} />
              )}
            </div>
          </div>
        )}

        {/* Product Modal */}
        {isProductModalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(10px)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '520px', width: '100%', padding: '2rem', position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>{editingProductId ? 'Edit Product' : 'Add New Product'}</h3>
                <button onClick={() => setIsProductModalOpen(false)} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>
                  <X size={20} />
                </button>
              </div>

              <div className="input-group">
                <label>Product Title</label>
                <input type="text" placeholder="e.g. Wireless Headset" value={prodTitle} onChange={(e) => setProdTitle(e.target.value)} />
              </div>

              <div className="input-group">
                <label>Price ($ USD)</label>
                <input type="number" step="0.01" placeholder="e.g. 99.99" value={prodPrice} onChange={(e) => setProdPrice(e.target.value)} />
              </div>

              <div className="input-group">
                <label>Description</label>
                <textarea rows="3" placeholder="Product details..." value={prodDescription} onChange={(e) => setProdDescription(e.target.value)} />
              </div>

              <div className="input-group">
                <label>Product Buy URL</label>
                <input type="url" placeholder="https://store.com/product/123" value={prodUrl} onChange={(e) => setProdUrl(e.target.value)} />
              </div>

              <div className="input-group">
                <label>Image URL</label>
                <input type="url" placeholder="https://images.unsplash.com/photo-..." value={prodImageUrl} onChange={(e) => setProdImageUrl(e.target.value)} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1.5rem' }}>
                <button className="btn btn-secondary" onClick={() => setIsProductModalOpen(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={handleSaveProduct} disabled={prodSubmitting}>
                  {prodSubmitting ? <span className="spinner"></span> : 'Save Product'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MediaCatalog;

