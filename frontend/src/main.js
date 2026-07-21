import './index.css';

// ============================================================================
// Organic Marketing AI - Frontend Application Logic
// ============================================================================

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

// Views Map
const views = {
  landing: document.getElementById('view-landing'),
  auth: document.getElementById('view-auth'),
  onboarding: document.getElementById('view-onboarding'),
  dashboard: document.getElementById('view-dashboard')
};

const nav = document.getElementById('main-nav');

// ============================================================================
// Utility Functions
// ============================================================================

function showToast(message, isError = false) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `message ${isError ? 'error' : 'success'}`;
  
  // Re-trigger animation
  toast.style.animation = 'none';
  toast.offsetHeight; /* trigger reflow */
  toast.style.animation = null;

  setTimeout(() => {
    toast.classList.add('hidden');
  }, 4000);
}

function switchView(viewName) {
  Object.values(views).forEach(v => v.classList.add('hidden'));
  if (views[viewName]) {
    views[viewName].classList.remove('hidden');
  }
  
  // Show nav on dashboard/onboarding, hide on landing/auth
  if (viewName === 'dashboard' || viewName === 'onboarding') {
    nav.classList.remove('hidden');
  } else {
    nav.classList.add('hidden');
  }
}

// ============================================================================
// Landing Page Events
// ============================================================================
document.getElementById('btn-goto-login').addEventListener('click', () => {
  switchView('auth');
});

document.getElementById('btn-goto-pricing').addEventListener('click', () => {
  document.getElementById('pricing').scrollIntoView({ behavior: 'smooth' });
});

document.getElementById('btn-buy-now').addEventListener('click', () => {
  switchView('auth');
});

document.getElementById('auth-back').addEventListener('click', (e) => {
  e.preventDefault();
  switchView('landing');
});

// ============================================================================
// Authentication Logic
// ============================================================================

const authToggle = document.getElementById('auth-toggle');
const authTitle = document.getElementById('auth-title');
const authSubtitle = document.getElementById('auth-subtitle');
const authSubmitBtn = document.getElementById('auth-submit');
const authForm = document.getElementById('auth-form');

authToggle.addEventListener('click', (e) => {
  e.preventDefault();
  state.isLoginMode = !state.isLoginMode;
  
  if (state.isLoginMode) {
    authTitle.textContent = 'Welcome Back';
    authSubtitle.textContent = 'Sign in to continue to your dashboard.';
    authSubmitBtn.querySelector('.btn-text').textContent = 'Sign In';
    authToggle.textContent = 'Create an account instead';
  } else {
    authTitle.textContent = 'Create Account';
    authSubtitle.textContent = 'Start automating your organic marketing today.';
    authSubmitBtn.querySelector('.btn-text').textContent = 'Sign Up';
    authToggle.textContent = 'Already have an account? Sign in';
  }
});

authForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const email = document.getElementById('auth-email').value;
  const password = document.getElementById('auth-password').value;
  const spinner = authSubmitBtn.querySelector('.spinner');
  
  spinner.classList.remove('hidden');
  authSubmitBtn.disabled = true;

  try {
    const endpoint = state.isLoginMode ? '/auth/login' : '/auth/register';
    const payload = state.isLoginMode 
      ? `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`
      : JSON.stringify({ email, password });
      
    const headers = state.isLoginMode 
      ? { 'Content-Type': 'application/x-www-form-urlencoded' }
      : { 'Content-Type': 'application/json' };

    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers,
      body: payload
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || 'Authentication failed');
    }

    const data = await res.json();
    state.token = data.access_token;
    localStorage.setItem('token', state.token);

    // Fetch User Data to see if onboarding is complete
    await fetchUserData();

  } catch (err) {
    showToast(err.message, true);
  } finally {
    spinner.classList.add('hidden');
    authSubmitBtn.disabled = false;
  }
});

async function fetchUserData() {
  try {
    const res = await fetch(`${API_BASE}/users/me`, {
      headers: { 'Authorization': `Bearer ${state.token}` }
    });
    
    if (res.ok) {
      state.user = await res.json();
      localStorage.setItem('user', JSON.stringify(state.user));
      
      showToast('Welcome back!');
      checkRouting();
    } else {
      throw new Error('Failed to fetch user data');
    }
  } catch (err) {
    console.error(err);
    logout();
  }
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  switchView('landing');
}

document.getElementById('btn-logout-nav').addEventListener('click', logout);

// ============================================================================
// Routing & Onboarding Logic
// ============================================================================

function checkRouting() {
  if (!state.token || !state.user) {
    switchView('landing');
    return;
  }

  // Check Subscription and Profile
  const hasBusinessProfile = state.user.businessProfile !== null;
  const isSubscribed = state.user.subscriptionStatus === 'ACTIVE';

  if (!hasBusinessProfile || !isSubscribed) {
    switchView('onboarding');
    updateOnboardingView();
  } else {
    switchView('dashboard');
    initDashboard();
  }
}

function updateOnboardingView() {
  document.getElementById('onboarding-step-1').classList.add('hidden');
  document.getElementById('onboarding-step-2').classList.add('hidden');
  document.getElementById('onboarding-step-3').classList.add('hidden');
  
  document.getElementById('step-1-indicator').classList.remove('active');
  document.getElementById('step-2-indicator').classList.remove('active');
  document.getElementById('step-3-indicator').classList.remove('active');

  document.getElementById(`onboarding-step-${state.onboardingStep}`).classList.remove('hidden');
  for (let i = 1; i <= state.onboardingStep; i++) {
    document.getElementById(`step-${i}-indicator`).classList.add('active');
  }
}

// Step 1 Events
document.getElementById('btn-next-step-1').addEventListener('click', () => {
  const website = document.getElementById('onboard-website').value;
  const desc = document.getElementById('onboard-description').value;
  if (!website || !desc) {
    showToast('Please fill in all fields', true);
    return;
  }
  state.onboardingStep = 2;
  updateOnboardingView();
});

// Step 2 Events
const modelCards = document.querySelectorAll('.selection-card');
modelCards.forEach(card => {
  card.addEventListener('click', () => {
    modelCards.forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    state.selectedBusinessModel = card.dataset.model;
  });
});

document.getElementById('btn-prev-step-2').addEventListener('click', () => {
  state.onboardingStep = 1;
  updateOnboardingView();
});

document.getElementById('btn-next-step-2').addEventListener('click', async () => {
  if (!state.selectedBusinessModel) {
    showToast('Please select a business model', true);
    return;
  }

  // Save profile to backend
  try {
    const website = document.getElementById('onboard-website').value;
    const desc = document.getElementById('onboard-description').value;

    const res = await fetch(`${API_BASE}/users/me/business-profile`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify({
        website_url: website,
        description: desc,
        brand_voice: 'Professional and Engaging',
        target_audience: 'B2B/B2C'
      }) // Adjusting payload to match existing schema mostly
    });

    if (!res.ok) throw new Error('Failed to save profile');
    
    showToast('Profile saved!');
    state.onboardingStep = 3;
    updateOnboardingView();
  } catch (err) {
    showToast(err.message, true);
  }
});

// Step 3 Events (Mock Payment)
document.getElementById('btn-prev-step-3').addEventListener('click', () => {
  state.onboardingStep = 2;
  updateOnboardingView();
});

document.getElementById('btn-mock-pay').addEventListener('click', async () => {
  const btn = document.getElementById('btn-mock-pay');
  btn.textContent = 'Processing...';
  btn.disabled = true;
  
  // Simulate payment delay
  setTimeout(async () => {
    try {
      // For this hackathon version, we assume we update the user status directly
      // In reality, this would be a webhook from PayPal.
      showToast('Payment Successful! Subscription Activated.');
      
      // Update local state to bypass onboarding lock
      state.user.subscriptionStatus = 'ACTIVE';
      localStorage.setItem('user', JSON.stringify(state.user));
      
      setTimeout(() => {
        checkRouting();
      }, 1000);
      
    } catch(err) {
      showToast('Payment failed', true);
      btn.textContent = 'Pay with PayPal (Mock $17)';
      btn.disabled = false;
    }
  }, 1500);
});

// ============================================================================
// Dashboard Logic
// ============================================================================

function initDashboard() {
  // Reset media dropzone
  state.files = [];
  renderMediaGrid();
}

// Integrations
const btnConnectMeta = document.getElementById('btn-connect-meta');
if (btnConnectMeta) {
  btnConnectMeta.addEventListener('click', () => {
    // Mock connection
    document.getElementById('meta-disconnected').classList.add('hidden');
    document.getElementById('meta-connected').classList.remove('hidden');
    showToast('Meta accounts linked successfully!');
  });
}

document.getElementById('btn-save-meta').addEventListener('click', () => {
  showToast('Automation settings saved!');
});

// Media Upload
const dropzone = document.getElementById('media-dropzone');
const fileInput = document.getElementById('file-input');

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.style.borderColor = 'var(--primary-color)';
});
dropzone.addEventListener('dragleave', (e) => {
  e.preventDefault();
  dropzone.style.borderColor = 'var(--border-color)';
});
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.style.borderColor = 'var(--border-color)';
  handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

function handleFiles(files) {
  for(let file of files) {
    if(file.type.startsWith('image/') || file.type.startsWith('video/')) {
      state.files.push(file);
    }
  }
  renderMediaGrid();
}

function renderMediaGrid() {
  const grid = document.getElementById('media-preview-grid');
  grid.innerHTML = '';
  
  state.files.forEach(file => {
    const div = document.createElement('div');
    div.className = 'media-item';
    
    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      div.appendChild(img);
    } else {
      const vid = document.createElement('video');
      vid.src = URL.createObjectURL(file);
      div.appendChild(vid);
    }
    
    grid.appendChild(div);
  });
}

// Start Automation Mock
document.getElementById('btn-start-automation').addEventListener('click', () => {
  if (state.files.length === 0) {
    showToast('Please upload media for the campaign', true);
    return;
  }
  
  const btn = document.getElementById('btn-start-automation');
  const spinner = btn.querySelector('.spinner');
  
  spinner.classList.remove('hidden');
  btn.disabled = true;
  
  setTimeout(() => {
    spinner.classList.add('hidden');
    btn.disabled = false;
    
    state.files = [];
    renderMediaGrid();
    
    showToast('Campaign Generated! Marketing loop scheduled successfully.');
  }, 2500);
});

// ============================================================================
// Initialization
// ============================================================================
checkRouting();
