import React from 'react';
import PostShipStudio from '../../components/PostShipStudio';
import NewsPosts from '../../components/NewsPosts';
import { useWorkspace } from '../../components/WorkspaceContext';

export default function PostShip({ user, token, showToast, activeWorkspaceId }) {
  const { activeWorkspace } = useWorkspace();

  return (
    <div className="view">
      <div className="container" style={{ padding: '2.5rem 0', maxWidth: 1100 }}>
        {/* Above the composer on purpose: somebody opening this page usually
            does not have a topic in mind, and "what happened this week" is a
            better starting point than an empty box. */}
        <NewsPosts
          token={token}
          activeWorkspaceId={activeWorkspaceId}
          showToast={showToast}
          business={activeWorkspace}
        />

        <PostShipStudio
          token={token}
          showToast={showToast}
          activeWorkspaceId={activeWorkspaceId}
          businessName={activeWorkspace?.name || 'Organiflo'}
        />
      </div>
    </div>
  );
}
