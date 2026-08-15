// The fallback is only reached when VITE_API_URL is unset — a local run or a
// preview deploy that did not inherit the env var. It pointed at
// organic-marketing-ai1 long after that service was migrated away from, so
// every such build silently talked to a dead host.
export const API_BASE = import.meta.env.VITE_API_URL || 'https://organic-marketing-ai-0abh.onrender.com/api/v1';

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

    // 402 is the server saying a plan limit stopped this request, and it sends
    // a written explanation with it ("You have used all 5 published posts...").
    // That message is the single most valuable thing this product ever says to
    // a free account, and every caller was dropping it into a generic red
    // toast. Surfaced globally instead, from the one place every authenticated
    // request already passes through.
    //
    // The response is cloned, not consumed: callers still read their own body
    // and their own error handling runs unchanged. This is additive.
    if (res.status === 402) {
      res.clone().json()
        .then((body) => {
          window.dispatchEvent(new CustomEvent('organiflo:upgrade-required', {
            detail: { message: body?.detail || body?.message || '' },
          }));
        })
        .catch(() => {
          window.dispatchEvent(new CustomEvent('organiflo:upgrade-required', {
            detail: { message: '' },
          }));
        });
    }

    return res;
  } catch (err) {
    if (err.message === 'Session expired. Please log in again.') throw err;
    throw new Error('Network error. Please check your connection.');
  }
};
