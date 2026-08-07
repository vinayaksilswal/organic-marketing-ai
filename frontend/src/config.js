export const API_BASE = import.meta.env.VITE_API_URL || 'https://organic-marketing-ai1.onrender.com/api/v1';

export const authFetch = async (url, options = {}, token, onLogout) => {
  const activeWorkspaceId = localStorage.getItem('activeWorkspaceId');
  // FormData must NOT carry an explicit Content-Type: the browser has to set
  // it itself so it can append the multipart boundary. Forcing application/json
  // here made every file upload through authFetch unparseable server-side.
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(activeWorkspaceId ? { 'X-Workspace-Id': activeWorkspaceId } : {}),
    ...(options.headers || {}),
  };

  try {
    // A caller passing an empty X-Workspace-Id is saying "this request is not
  // about one workspace". Send no header at all rather than an empty one,
  // which the server would try to resolve and refuse.
  if (headers['X-Workspace-Id'] === '') delete headers['X-Workspace-Id'];

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
