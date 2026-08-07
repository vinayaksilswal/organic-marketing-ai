import { createContext, useContext, useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../config';

const WorkspaceContext = createContext();

export const useWorkspace = () => useContext(WorkspaceContext);

export const WorkspaceProvider = ({ children, token, onLogout }) => {
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(
    localStorage.getItem('activeWorkspaceId') || null
  );
  const [loading, setLoading] = useState(true);

  const fetchWorkspaces = async () => {
    if (!token) return;
    try {
      setLoading(true);
      // Deliberately sent with an empty workspace header.
      //
      // The active workspace is kept in localStorage, which is shared by every
      // account that signs in on this browser. A second user inherits the
      // first user's id and the server correctly refuses it -- including on
      // THIS call, which is the only one that could have corrected the stale
      // value. The dashboard then 404s on everything, permanently, and the
      // only way out is clearing site data.
      //
      // This request asks "which workspaces are mine", so it must not carry an
      // assumption about which one is current.
      const res = await authFetch(
        `${API_BASE}/businesses`, { headers: { 'X-Workspace-Id': '' } }, token, onLogout
      );
      if (!res.ok) throw new Error(`Failed to fetch workspaces (${res.status})`);
      const data = await res.json();
      setWorkspaces(data);

      if (data.length > 0) {
        if (!activeWorkspaceId || !data.find(w => w.id === activeWorkspaceId)) {
          setActiveWorkspace(data[0].id);
        }
      } else {
        setActiveWorkspace(null);
      }
    } catch (err) {
      console.error('Error fetching workspaces:', err);
      // A workspace id that cannot be resolved is worse than none: every
      // subsequent request carries it and is refused. Dropping it means the
      // next load starts clean rather than repeating the same failure.
      if (activeWorkspaceId) {
        console.warn('Clearing unusable active workspace', activeWorkspaceId);
        setActiveWorkspace(null);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, [token]);

  const setActiveWorkspace = (id) => {
    setActiveWorkspaceId(id);
    if (id) {
      localStorage.setItem('activeWorkspaceId', id);
    } else {
      localStorage.removeItem('activeWorkspaceId');
    }
  };

  return (
    <WorkspaceContext.Provider value={{
      workspaces,
      activeWorkspaceId,
      activeWorkspace: workspaces.find(w => w.id === activeWorkspaceId),
      setActiveWorkspace,
      refreshWorkspaces: fetchWorkspaces,
      loading
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
};
