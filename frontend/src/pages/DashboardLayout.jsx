import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Logo from '../components/Logo';
import Sidebar from '../components/Sidebar';
import Overview from './dashboard/Overview';
import VideoStudio from './dashboard/VideoStudio';
import MediaCatalog from './dashboard/MediaCatalog';
import SocialScheduler from './dashboard/SocialScheduler';
import EmailSuite from './dashboard/EmailSuite';
import Workspaces from './dashboard/Workspaces';
import TeamManagement from './dashboard/TeamManagement';
import Billing from './dashboard/Billing';
import Support from './dashboard/Support';
import AdminSupport from './dashboard/AdminSupport';
import { useWorkspace } from '../components/WorkspaceContext';
import HelpWidget from '../components/HelpWidget';
import SystemBanner from '../components/SystemBanner';
import DesktopHint from '../components/DesktopHint';

const DashboardLayout = ({ user, token, showToast, onLogout, updateAuth }) => {
  const { activeWorkspaceId, setActiveWorkspace, workspaces } = useWorkspace();

  const userWithWorkspaces = {
    ...user,
    businessProfiles: workspaces && workspaces.length > 0 ? workspaces : (user?.businessProfiles || [])
  };

  // The sidebar is a fixed 260px column on desktop and a slide-out drawer on
  // a phone, where 260px of a 390px screen is most of the screen.
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  // Close the drawer whenever the route changes. Leaving it open over the
  // page the user just chose means every navigation needs two taps: one to
  // pick, one to dismiss.
  useEffect(() => { setNavOpen(false); }, [location.pathname]);

  // A drawer that scrolls the page behind it is disorienting on touch.
  useEffect(() => {
    document.body.style.overflow = navOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [navOpen]);

  return (
    <div className="dash-shell" style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-dark)' }}>
      {/* Phone-only bar. Holds the one control a drawer needs and the brand,
          so there is always a way back to the top level. */}
      <header className="dash-topbar">
        <button
          onClick={() => setNavOpen(true)}
          aria-label="Open menu"
          aria-expanded={navOpen}
          className="dash-burger"
        >
          <Menu size={20} />
        </button>
        <Logo size={30} showWordmark noTagline />
      </header>

      {/* Tapping the dimmed page closes the drawer — the gesture every phone
          user already expects, and it needs no explaining. */}
      {navOpen && (
        <div className="dash-scrim" onClick={() => setNavOpen(false)} aria-hidden="true" />
      )}

      <div className={`dash-nav ${navOpen ? 'open' : ''}`}>
        <Sidebar
          user={userWithWorkspaces}
          token={token}
          activeWorkspaceId={activeWorkspaceId}
          onWorkspaceChange={setActiveWorkspace}
          onLogout={onLogout}
        />
      </div>

      <div className="dash-main" style={{ flex: 1, overflowY: 'auto', minWidth: 0 }}>
        <SystemBanner />
        {/* Renders nothing above 900px, and nothing at all once dismissed. */}
        <DesktopHint />
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
          <Route path="/support" element={<Support user={user} token={token} showToast={showToast} />} />
          {/* Not linked in the sidebar for anyone. The API answers 404 to a
              non-admin, so the page renders empty rather than confirming an
              admin area exists. */}
          <Route path="/inbox" element={<AdminSupport user={user} token={token} showToast={showToast} />} />
        </Routes>
      </div>
      <HelpWidget />
    </div>
  );
};

export default DashboardLayout;
