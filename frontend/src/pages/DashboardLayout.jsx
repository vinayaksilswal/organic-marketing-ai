import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import Overview from './dashboard/Overview';
import VideoStudio from './dashboard/VideoStudio';
import MediaCatalog from './dashboard/MediaCatalog';
import SocialScheduler from './dashboard/SocialScheduler';
import EmailSuite from './dashboard/EmailSuite';
import Workspaces from './dashboard/Workspaces';
import TeamManagement from './dashboard/TeamManagement';
import { useWorkspace } from '../components/WorkspaceContext';
import HelpWidget from '../components/HelpWidget';

const DashboardLayout = ({ user, token, showToast, onLogout, updateAuth }) => {
  const { activeWorkspaceId, setActiveWorkspace, workspaces } = useWorkspace();

  const userWithWorkspaces = {
    ...user,
    businessProfiles: workspaces && workspaces.length > 0 ? workspaces : (user?.businessProfiles || [])
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-dark)' }}>
      <Sidebar 
        user={userWithWorkspaces} 
        activeWorkspaceId={activeWorkspaceId} 
        onWorkspaceChange={setActiveWorkspace} 
      />
      
      <div style={{ flex: 1, marginLeft: '260px', overflowY: 'auto' }}>
        <Routes>
          <Route path="/" element={<Overview user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/video-studio" element={<VideoStudio user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/media-catalog" element={<MediaCatalog user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/social-scheduler" element={<SocialScheduler user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/email-suite" element={<EmailSuite user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/workspaces" element={<Workspaces user={user} token={token} showToast={showToast} updateAuth={updateAuth} />} />
          <Route path="/team" element={<TeamManagement />} />
        </Routes>
      </div>
      <HelpWidget />
    </div>
  );
};

export default DashboardLayout;
