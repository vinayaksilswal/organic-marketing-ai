import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE, authFetch } from '../../config';
import { Users, Shield, UserPlus, Trash2, Check, Clock, Mail } from 'lucide-react';

const ROLES = [
  { value: 'viewer', label: 'Viewer', hint: 'Read-only access' },
  { value: 'editor', label: 'Editor', hint: 'Create and edit content' },
  { value: 'admin', label: 'Admin', hint: 'Full access except billing' },
];

export default function TeamManagement({ token, showToast, activeWorkspaceId }) {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('editor');
  const [inviting, setInviting] = useState(false);
  const [loadError, setLoadError] = useState(null);

  const inputStyle = {
    width: '100%', padding: '0.7rem 0.85rem', borderRadius: '8px',
    background: 'rgba(255,255,255,0.04)', color: '#fff',
    border: '1px solid rgba(255,255,255,0.1)', fontSize: '0.9rem', outline: 'none',
  };

  // showToast is deliberately NOT a dependency. It is redefined on every render
  // of the parent, so including it made loadMembers a new function each render,
  // which refired the effect, which toasted on failure, which re-rendered —
  // an endless request loop against /team.
  const loadMembers = useCallback(async () => {
    if (!activeWorkspaceId) { setLoading(false); setMembers([]); return; }
    setLoading(true);
    try {
      const res = await authFetch(`${API_BASE}/team`, {
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (!res.ok) {
        setLoadError(
          res.status === 400
            ? 'No business selected for this request.'
            : `Could not load team members (error ${res.status}).`
        );
        setMembers([]);
        return;
      }
      setMembers(await res.json());
      setLoadError(null);
    } catch {
      setLoadError('Could not reach the server to load your team.');
      setMembers([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeWorkspaceId, token]);

  useEffect(() => { loadMembers(); }, [loadMembers]);

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      const res = await authFetch(`${API_BASE}/team`, {
        method: 'POST',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
      }, token);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || 'Failed to send invite');
      showToast(`Invited ${inviteEmail.trim()}`);
      setInviteEmail('');
      loadMembers();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (memberId, role) => {
    try {
      const res = await authFetch(`${API_BASE}/team/${memberId}`, {
        method: 'PATCH',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
        body: JSON.stringify({ role }),
      }, token);
      if (!res.ok) throw new Error('Failed to update role');
      setMembers(ms => ms.map(m => (m.id === memberId ? { ...m, role } : m)));
      showToast('Role updated');
    } catch (err) {
      showToast(err.message, true);
    }
  };

  const handleRemove = async (member) => {
    try {
      const res = await authFetch(`${API_BASE}/team/${member.id}`, {
        method: 'DELETE',
        headers: { 'X-Workspace-Id': activeWorkspaceId },
      }, token);
      if (!res.ok) throw new Error('Failed to remove member');
      setMembers(ms => ms.filter(m => m.id !== member.id));
      showToast(`Removed ${member.email}`);
    } catch (err) {
      showToast(err.message, true);
    }
  };

  return (
    <div className="view">
      <div className="container" style={{ padding: '3rem 0', maxWidth: 900 }}>
        <div style={{ marginBottom: '2.5rem' }}>
          <h1 style={{ margin: 0, fontSize: '2rem', display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <Users size={28} color="var(--primary-color)" /> Team &amp; Roles
          </h1>
          <p className="text-muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.95rem' }}>
            Invite people to collaborate on this workspace and control what they can do.
          </p>
        </div>

        {!activeWorkspaceId ? (
          <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.55)' }}>
              Select a business from the sidebar to manage its team.
            </p>
          </div>
        ) : (
          <>
            {/* Invite */}
            <div className="glass-panel" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: '0 0 1.15rem 0', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <UserPlus size={17} color="var(--primary-color)" /> Invite a teammate
              </h2>
              <form onSubmit={handleInvite} style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div style={{ flex: '1 1 260px', position: 'relative' }}>
                  <Mail size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.35)' }} />
                  <input
                    type="email" required placeholder="colleague@company.com"
                    value={inviteEmail} onChange={e => setInviteEmail(e.target.value)}
                    style={{ ...inputStyle, paddingLeft: '2.35rem' }}
                  />
                </div>
                <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
                  style={{ ...inputStyle, width: 'auto', minWidth: 150, appearance: 'auto' }}>
                  {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
                <button type="submit" className="btn btn-primary" disabled={inviting}
                  style={{ padding: '0.7rem 1.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  {inviting ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <UserPlus size={15} />}
                  {inviting ? 'Sending…' : 'Send Invite'}
                </button>
              </form>
              <p style={{ margin: '0.85rem 0 0 0', fontSize: '0.8rem', color: 'rgba(255,255,255,0.4)' }}>
                {ROLES.find(r => r.value === inviteRole)?.hint}
              </p>
            </div>

            {/* Members */}
            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{ padding: '1.15rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <Shield size={16} color="#60a5fa" />
                <h2 style={{ margin: 0, fontSize: '1rem' }}>Workspace members ({members.length})</h2>
              </div>

              {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'rgba(255,255,255,0.4)' }}>
                  <span className="spinner" style={{ width: 20, height: 20 }} />
                </div>
              ) : loadError ? (
                <div style={{ padding: '2.5rem 2rem', textAlign: 'center' }}>
                  <p style={{ margin: '0 0 0.85rem 0', color: '#fca5a5', fontSize: '0.9rem' }}>{loadError}</p>
                  <button className="btn btn-secondary" onClick={loadMembers}
                    style={{ padding: '0.45rem 0.9rem', fontSize: '0.83rem' }}>
                    Retry
                  </button>
                </div>
              ) : members.length === 0 ? (
                <div style={{ padding: '3rem 2rem', textAlign: 'center' }}>
                  <p style={{ margin: 0, color: 'rgba(255,255,255,0.5)', fontSize: '0.9rem' }}>
                    No teammates yet. Invite someone above to collaborate on this workspace.
                  </p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                        {['Member', 'Role', 'Status', ''].map((h, i) => (
                          <th key={i} style={{ padding: '0.75rem 1.5rem', textAlign: i === 3 ? 'right' : 'left', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'rgba(255,255,255,0.4)', fontWeight: 600 }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {members.map(m => (
                        <tr key={m.id} style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '0.9rem 1.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg, var(--primary-color), var(--secondary-color))', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: '0.85rem', flexShrink: 0 }}>
                                {m.email.charAt(0).toUpperCase()}
                              </div>
                              <span style={{ fontSize: '0.88rem' }}>{m.email}</span>
                            </div>
                          </td>
                          <td style={{ padding: '0.9rem 1.5rem' }}>
                            <select value={m.role} onChange={e => handleRoleChange(m.id, e.target.value)}
                              style={{ ...inputStyle, width: 'auto', padding: '0.35rem 0.55rem', fontSize: '0.82rem', appearance: 'auto' }}>
                              {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                            </select>
                          </td>
                          <td style={{ padding: '0.9rem 1.5rem' }}>
                            {m.status === 'active' ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', color: '#10b981' }}>
                                <Check size={13} /> Active
                              </span>
                            ) : (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', color: '#f59e0b' }}>
                                <Clock size={13} /> Pending
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '0.9rem 1.5rem', textAlign: 'right' }}>
                            <button onClick={() => handleRemove(m)} title={`Remove ${m.email}`}
                              style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', padding: '0.35rem', borderRadius: 6, display: 'inline-flex' }}
                              onMouseEnter={e => { e.currentTarget.style.color = '#f87171'; }}
                              onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.35)'; }}>
                              <Trash2 size={15} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
