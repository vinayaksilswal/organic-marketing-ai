import React from 'react';
import PostShipStudio from '../../components/PostShipStudio';
import { useWorkspace } from '../../components/WorkspaceContext';

export default function PostShip({ user, token, showToast, activeWorkspaceId }) {
  const { activeWorkspace } = useWorkspace();

  return (
    <div className="view">
      <div className="container" style={{ padding: '2.5rem 0', maxWidth: 1100 }}>
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
