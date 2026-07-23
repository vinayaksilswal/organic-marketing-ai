import { createContext, useContext, useState, useEffect } from 'react';
import { API_BASE, authFetch } from '../App';

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
      const res = await authFetch(`${API_BASE}/businesses`, {}, token, onLogout);
      if (!res.ok) throw new Error('Failed to fetch workspaces');
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
