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
import Billing from './dashboard/Billing';
import { useWorkspace } from '../components/WorkspaceContext';
import HelpWidget from '../components/HelpWidget';
import SystemBanner from '../components/SystemBanner';

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
        token={token}
        activeWorkspaceId={activeWorkspaceId}
        onWorkspaceChange={setActiveWorkspace}
        onLogout={onLogout}
      />
      
      <div style={{ flex: 1, marginLeft: '260px', overflowY: 'auto' }}>
        <SystemBanner />
        <Routes>
          {/* onLogout reaches Overview so its Log out button clears React
              state through the router, rather than falling back to wiping
              localStorage and hard-reloading the page. */}
          <Route path="/" element={<Overview user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} onLogout={onLogout} />} />
          <Route path="/video-studio" element={<VideoStudio user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/media-catalog" element={<MediaCatalog user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/social-scheduler" element={<SocialScheduler user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/email-suite" element={<EmailSuite user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/workspaces" element={<Workspaces user={user} token={token} showToast={showToast} updateAuth={updateAuth} />} />
          <Route path="/team" element={<TeamManagement user={user} token={token} showToast={showToast} activeWorkspaceId={activeWorkspaceId} />} />
          <Route path="/billing" element={<Billing user={user} token={token} showToast={showToast} />} />
        </Routes>
      </div>
      <HelpWidget />
    </div>
  );
};

export default DashboardLayout;
