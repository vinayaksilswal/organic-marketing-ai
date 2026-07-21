import './index.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// State
let state = {
  token: localStorage.getItem('token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  isLoginMode: true,
  onboardingStep: 1,
  selectedBusinessModel: null,
  files: []
};

// DOM Elements
const views = {
  auth: document.getElementById('view-auth'),
  onboarding: document.getElementById('view-onboarding'),
  dashboard: document.getElementById('view-dashboard')
};

// Helpers
const showToast = (message, type = 'success') => {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `message ${type}`;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 3000);
};

const showView = (viewName) => {
  Object.values(views).forEach(v => v.classList.add('hidden'));
  document.getElementById('app').classList.toggle('centered-layout', viewName !== 'dashboard');
  if (views[viewName]) views[viewName].classList.remove('hidden');
};

const setLoading = (btnId, isLoading) => {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  const text = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner');
  
  if (isLoading) {
    text.classList.add('hidden');
    spinner.classList.remove('hidden');
    btn.disabled = true;
  } else {
    text.classList.remove('hidden');
    spinner.classList.add('hidden');
    btn.disabled = false;
  }
};

// API Fetch Wrapper
const apiCall = async (endpoint, options = {}) => {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  
  // Don't set content-type for FormData
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: { ...headers, ...options.headers }
  });
  
  if (response.status === 401) {
    logout();
    throw new Error('Unauthorized');
  }
  
  return response.json();
};

// ------------------------------------------------------------------
// Routing Logic
// ------------------------------------------------------------------
const initializeApp = async () => {
  if (!state.token) {
    showView('auth');
    return;
  }

  try {
    // Check if business profile exists
    const res = await apiCall('/user/business-profile');
    if (res.success && res.data) {
      showView('dashboard');
      initDashboard();
    } else {
      showView('onboarding');
    }
  } catch (e) {
    console.error(e);
    showToast('Failed to connect to backend server. Please make sure it is running on port 8000.', 'error');
  }
};

const logout = () => {
  state.token = null;
  state.user = null;
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  showView('auth');
};

// ------------------------------------------------------------------
// Auth Handlers
// ------------------------------------------------------------------
document.getElementById('auth-toggle').addEventListener('click', (e) => {
  e.preventDefault();
  state.isLoginMode = !state.isLoginMode;
  document.getElementById('auth-title').textContent = state.isLoginMode ? 'Welcome Back' : 'Create Account';
  document.getElementById('auth-subtitle').textContent = state.isLoginMode ? 'Sign in to continue to your dashboard.' : 'Enter your details to get started.';
  document.getElementById('auth-submit').querySelector('.btn-text').textContent = state.isLoginMode ? 'Sign In' : 'Sign Up';
  e.target.textContent = state.isLoginMode ? 'Create an account instead' : 'Sign in instead';
});

document.getElementById('auth-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const email = document.getElementById('auth-email').value;
  const password = document.getElementById('auth-password').value;
  
  setLoading('auth-submit', true);
  try {
    const endpoint = state.isLoginMode ? '/auth/login' : '/auth/register';
    const res = await apiCall(endpoint, {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });

    if (res.success) {
      state.token = res.token;
      state.user = res.user;
      localStorage.setItem('token', res.token);
      localStorage.setItem('user', JSON.stringify(res.user));
      showToast('Authentication successful!');
      initializeApp();
    } else {
      showToast(res.message || 'Authentication failed', 'error');
    }
  } catch (err) {
    showToast('Network error', 'error');
  } finally {
    setLoading('auth-submit', false);
  }
});

document.getElementById('btn-logout').addEventListener('click', logout);

// ------------------------------------------------------------------
// Onboarding Handlers
// ------------------------------------------------------------------
document.getElementById('btn-next-step').addEventListener('click', () => {
  const url = document.getElementById('onboard-website').value;
  if (!url) return showToast('Please enter website URL', 'error');
  
  document.getElementById('onboarding-step-1').classList.add('hidden');
  document.getElementById('onboarding-step-2').classList.remove('hidden');
  document.getElementById('step-1-indicator').classList.add('active');
  document.getElementById('step-2-indicator').classList.add('active');
});

document.getElementById('btn-prev-step').addEventListener('click', () => {
  document.getElementById('onboarding-step-2').classList.add('hidden');
  document.getElementById('onboarding-step-1').classList.remove('hidden');
  document.getElementById('step-2-indicator').classList.remove('active');
});

document.querySelectorAll('.selection-card').forEach(card => {
  card.addEventListener('click', () => {
    document.querySelectorAll('.selection-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.selectedBusinessModel = card.dataset.model;
  });
});

document.getElementById('btn-finish-onboarding').addEventListener('click', async () => {
  if (!state.selectedBusinessModel) return showToast('Please select a business model', 'error');
  
  const websiteUrl = document.getElementById('onboard-website').value;
  const description = document.getElementById('onboard-description').value;
  
  setLoading('btn-finish-onboarding', true);
  try {
    const res = await apiCall('/user/business-profile', {
      method: 'PUT',
      body: JSON.stringify({ websiteUrl, description, businessModel: state.selectedBusinessModel })
    });
    if (res.success) {
      showToast('Profile created successfully!');
      showView('dashboard');
      initDashboard();
    }
  } catch (err) {
    showToast('Failed to save profile', 'error');
  } finally {
    setLoading('btn-finish-onboarding', false);
  }
});

// ------------------------------------------------------------------
// Dashboard & Meta Integration
// ------------------------------------------------------------------
const initDashboard = async () => {
  try {
    const res = await apiCall('/user/social-connection');
    if (res.success && res.data && res.data.fbAccessToken) {
      document.getElementById('meta-disconnected').classList.add('hidden');
      document.getElementById('meta-connected').classList.remove('hidden');
    }
  } catch (e) {
    console.error(e);
  }
};

document.getElementById('btn-connect-meta').addEventListener('click', async () => {
  // Mock OAuth Flow
  setLoading('btn-connect-meta', true);
  setTimeout(async () => {
    try {
      const res = await apiCall('/user/social-connection', {
        method: 'PUT',
        body: JSON.stringify({
          fbAccessToken: 'mock-token-123',
          fbPageId: 'page1',
          fbPageName: 'My E-commerce Page',
          igAccountId: 'ig1',
          igAccountName: '@myecommerce'
        })
      });
      if (res.success) {
        showToast('Meta accounts connected successfully!');
        document.getElementById('meta-disconnected').classList.add('hidden');
        document.getElementById('meta-connected').classList.remove('hidden');
      }
    } catch (e) {
      showToast('Failed to connect Meta', 'error');
    } finally {
      setLoading('btn-connect-meta', false);
    }
  }, 1000);
});

document.getElementById('btn-save-meta').addEventListener('click', () => {
  showToast('Meta settings saved');
});

// ------------------------------------------------------------------
// Media Drag & Drop
// ------------------------------------------------------------------
const dropzone = document.getElementById('media-dropzone');
const fileInput = document.getElementById('file-input');
const previewGrid = document.getElementById('media-preview-grid');

dropzone.addEventListener('click', () => fileInput.click());

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  dropzone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
  dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
  dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
});

dropzone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files));
fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(newFiles) {
  Array.from(newFiles).forEach(file => {
    if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) return;
    state.files.push(file);
    renderPreview(file);
  });
}

function renderPreview(file) {
  const div = document.createElement('div');
  div.className = 'media-item';
  
  const removeBtn = document.createElement('button');
  removeBtn.className = 'remove-media';
  removeBtn.innerHTML = '✕';
  removeBtn.onclick = () => {
    state.files = state.files.filter(f => f !== file);
    div.remove();
  };
  
  let media;
  if (file.type.startsWith('image/')) {
    media = document.createElement('img');
    media.src = URL.createObjectURL(file);
  } else {
    media = document.createElement('video');
    media.src = URL.createObjectURL(file);
  }
  
  div.appendChild(media);
  div.appendChild(removeBtn);
  previewGrid.appendChild(div);
}

// ------------------------------------------------------------------
// Start Automation
// ------------------------------------------------------------------
document.getElementById('btn-start-automation').addEventListener('click', async () => {
  if (state.files.length === 0) {
    return showToast('Please upload at least one media file', 'error');
  }

  setLoading('btn-start-automation', true);
  try {
    let uploadedUrls = [];
    
    // Upload each file to backend
    for (const file of state.files) {
      const formData = new FormData();
      formData.append('file', file);
      
      const uploadRes = await apiCall('/upload-media', {
        method: 'POST',
        body: formData
      });
      if (uploadRes.success && uploadRes.data.url) {
        uploadedUrls.push(uploadRes.data.url);
      }
    }

    // Trigger Campaign creation
    const campaignRes = await apiCall('/campaigns', {
      method: 'POST',
      body: JSON.stringify({
        baseCaption: "Automated Campaign Generated via Frontend",
        mediaUrl: uploadedUrls[0],
        mediaType: state.files[0].type
      })
    });

    if (campaignRes.success) {
      // Trigger Manual Social Post
      const formData = new FormData();
      formData.append('platform', 'BOTH');
      formData.append('generate_ai_caption', 'true');
      formData.append('product_id', campaignRes.data.id);
      
      await fetch(`${API_BASE}/posts/manual`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${state.token}` },
        body: formData
      });

      showToast('Automation started successfully! Your post is being generated.');
      
      // Reset files
      state.files = [];
      previewGrid.innerHTML = '';
    } else {
      showToast('Failed to create campaign', 'error');
    }

  } catch (err) {
    console.error(err);
    showToast('Failed to start automation', 'error');
  } finally {
    setLoading('btn-start-automation', false);
  }
});

// Boot
initializeApp();
