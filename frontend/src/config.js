export const API_BASE = import.meta.env.VITE_API_URL || 'https://organic-marketing-ai1.onrender.com/api/v1';

export const authFetch = async (url, options = {}, token, onLogout) => {
  const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {}),
    ...(options.headers || {}),
  };

  try {
    const res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      if (onLogout) onLogout();
      throw new Error('Session expired. Please log in again.');
    }

    return res;
  } catch (err) {
    if (err.message === 'Session expired. Please log in again.') throw err;
    throw new Error('Network error. Please check your connection.');
  }
};
